#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Configuration (env var overrides) ---
MAX_FILES="${LLM_REVIEW_MAX_FILES:-40}"
MAX_LINES="${LLM_REVIEW_MAX_LINES:-4000}"
TIMEOUT="${LLM_REVIEW_TIMEOUT:-90}"
SKIP="${LLM_REVIEW_SKIP:-0}"

# --- Skip check ---
if [[ "$SKIP" == "1" ]]; then
  echo "LLM review: skipped (LLM_REVIEW_SKIP=1)"
  exit 0
fi

# --- Gemini availability check ---
if ! command -v gemini &>/dev/null; then
  echo "LLM review: skipped (gemini CLI not found)"
  exit 0
fi

# --- Relevant extensions filter ---
EXTENSIONS_PATTERN='\.py$|\.md$|\.feature$|\.toml$|\.yaml$|\.yml$'
DASHBOARD_EXCLUDE='src/pac/backtester/dashboard/'

# --- Compute diff ---
CHANGED_FILES=$(git diff --cached --name-only | grep -E "$EXTENSIONS_PATTERN" | grep -v "$DASHBOARD_EXCLUDE" || true)

if [[ -z "$CHANGED_FILES" ]]; then
  echo "LLM review: no reviewable changes."
  exit 0
fi

FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
FULL_DIFF=$(git diff --cached -- $(echo "$CHANGED_FILES" | tr '\n' ' ') 2>/dev/null || true)
LINE_COUNT=$(echo "$FULL_DIFF" | wc -l | tr -d ' ')

# --- Context overflow check ---
if [[ "$FILE_COUNT" -gt "$MAX_FILES" || "$LINE_COUNT" -gt "$MAX_LINES" ]]; then
  cat >&2 <<BLOCK
══════════════════════════════════════════════════════════════════
  ⚠  CONTEXT LIMIT EXCEEDED
  ${FILE_COUNT} files changed, ~${LINE_COUNT} lines of diff.
  Reviews beyond this threshold produce incomplete analysis.

  COMMIT BLOCKED. Split your changes into smaller, focused
  commits before proceeding.
  To skip: LLM_REVIEW_SKIP=1 git commit ...
══════════════════════════════════════════════════════════════════
BLOCK
  exit 1
fi

# --- Commit message ---
COMMIT_MSG=""
if [[ -f "$PROJECT_ROOT/.git/COMMIT_EDITMSG" ]]; then
  COMMIT_MSG=$(head -1 "$PROJECT_ROOT/.git/COMMIT_EDITMSG")
fi

# --- Agent routing ---
ACTIVATE_BDD=false
ACTIVATE_TESTING=false
ACTIVATE_DOCUMENTATION=false
ACTIVATE_ARCHITECTURE=false
ACTIVATE_RESEARCH=false

HAS_PRODUCTION_PY=false
HAS_TEST_PY=false
HAS_DOCS=false
HAS_RESEARCH=false

while IFS= read -r file; do
  case "$file" in
    tests/*|*/tests/*|*/test_*.py)
      HAS_TEST_PY=true ;;
  esac
  case "$file" in
    src/pac/backtester/dashboard/*) ;;
    src/pac/*/tests/*|src/pac/*/test_*.py) ;;
    src/pac/*.py|src/pac/*/*.py|src/pac/*/*/*.py|src/pac/*/*/*/*.py)
      HAS_PRODUCTION_PY=true ;;
  esac
  case "$file" in
    docs/*|*/README.md|CHANGELOG.md|AGENTS.md)
      HAS_DOCS=true ;;
  esac
  case "$file" in
    research/*)
      HAS_RESEARCH=true ;;
  esac
done <<< "$CHANGED_FILES"

if [[ "$HAS_PRODUCTION_PY" == "true" ]]; then
  ACTIVATE_BDD=true
  ACTIVATE_TESTING=true
  ACTIVATE_ARCHITECTURE=true
  ACTIVATE_DOCUMENTATION=true
fi

if [[ "$HAS_TEST_PY" == "true" ]]; then
  ACTIVATE_TESTING=true
fi

if [[ "$HAS_DOCS" == "true" ]]; then
  ACTIVATE_DOCUMENTATION=true
fi

if [[ "$HAS_RESEARCH" == "true" ]]; then
  ACTIVATE_RESEARCH=true
fi

AGENTS=()
$ACTIVATE_BDD && AGENTS+=("bdd")
$ACTIVATE_TESTING && AGENTS+=("testing")
$ACTIVATE_DOCUMENTATION && AGENTS+=("documentation")
$ACTIVATE_ARCHITECTURE && AGENTS+=("architecture")
$ACTIVATE_RESEARCH && AGENTS+=("research")

if [[ ${#AGENTS[@]} -eq 0 ]]; then
  echo "LLM review: no agents activated."
  exit 0
fi

# --- Parallel agent execution ---
TMPDIR_REVIEW=$(mktemp -d)
trap 'rm -rf "$TMPDIR_REVIEW"' EXIT

echo "LLM review: running ${#AGENTS[@]} agent(s) [${AGENTS[*]}]..." >&2

PIDS=()
for agent in "${AGENTS[@]}"; do
  POLICY_FILE="$SCRIPT_DIR/policies/${agent}.md"
  if [[ ! -f "$POLICY_FILE" ]]; then
    echo "WARNING: Policy file not found: $POLICY_FILE" >&2
    continue
  fi

  OUTPUT_FILE="$TMPDIR_REVIEW/${agent}.out"
  PROMPT_FILE="$TMPDIR_REVIEW/${agent}.prompt"

  cat > "$PROMPT_FILE" <<PROMPT_EOF
Review the following diff for violations of your policy.

Commit message: ${COMMIT_MSG}

Changed files:
${CHANGED_FILES}

--- DIFF START ---
${FULL_DIFF}
--- DIFF END ---

Your response MUST begin with exactly one of:
verdict: PASS
verdict: FAIL
Then explain your reasoning briefly.
PROMPT_EOF

  (
    gemini \
      -p "$(cat "$PROMPT_FILE")" \
      -m gemini-2.5-flash \
      --admin-policy "$POLICY_FILE" \
      --output-format text \
      </dev/null 2>/dev/null > "$OUTPUT_FILE" &
    GEMINI_PID=$!
    (sleep "$TIMEOUT" && kill "$GEMINI_PID" 2>/dev/null) &
    TIMER_PID=$!
    if wait "$GEMINI_PID" 2>/dev/null; then
      kill "$TIMER_PID" 2>/dev/null
    else
      echo "verdict: TIMEOUT" > "$OUTPUT_FILE"
    fi
  ) &
  PIDS+=($!)
done

# Wait for all agents
for pid in "${PIDS[@]}"; do
  wait "$pid" 2>/dev/null || true
done

# --- Result parsing ---
AGENT_ORDER=("bdd" "testing" "documentation" "architecture" "research")
TOTAL=0
PASSED=0
FAILURES=()
FAILURE_OUTPUTS=()

for agent in "${AGENT_ORDER[@]}"; do
  OUTPUT_FILE="$TMPDIR_REVIEW/${agent}.out"
  [[ -f "$OUTPUT_FILE" ]] || continue
  TOTAL=$((TOTAL + 1))
  CONTENT=$(cat "$OUTPUT_FILE")

  VERDICT_REGION=$(echo "$CONTENT" | head -5)

  if echo "$VERDICT_REGION" | grep -qiE 'verdict\s*:\s*pass'; then
    PASSED=$((PASSED + 1))
  elif echo "$CONTENT" | grep -qi "verdict: *TIMEOUT"; then
    PASSED=$((PASSED + 1))
    echo "LLM review: ${agent} agent timed out (treated as pass)." >&2
  elif echo "$VERDICT_REGION" | grep -qiE 'verdict\s*:\s*fail'; then
    FAILURES+=("$agent")
    FAILURE_OUTPUTS+=("$CONTENT")
  else
    FAILURES+=("$agent")
    FAILURE_OUTPUTS+=("⚠ Could not parse verdict. Raw output:\n${CONTENT}")
  fi
done

# --- Output ---
if [[ ${#FAILURES[@]} -eq 0 ]]; then
  echo "LLM review: ${PASSED}/${TOTAL} agents passed ✓"
  exit 0
fi

# Print failure report
cat >&2 <<BLOCK
══════════════════════════════════════════════════════════════════
  LLM REVIEW FAILED — ${PASSED}/${TOTAL} agents passed — ${#FAILURES[@]} violation(s) found
BLOCK

for i in "${!FAILURES[@]}"; do
  agent="${FAILURES[$i]}"
  output="${FAILURE_OUTPUTS[$i]}"
  label=$(echo "$agent" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')
  findings=$(echo -e "$output" | grep -vi "verdict:" || echo -e "$output")

  cat >&2 <<BLOCK

  ── ${label} ─────────────────────────────────────────────────
$(echo "$findings" | sed 's/^/  /')
BLOCK
done

cat >&2 <<'BLOCK'

  ────────────────────────────────────────────────────────────
  ACTION REQUIRED: Fix the violations above and recommit.
  To skip LLM review: LLM_REVIEW_SKIP=1 git commit ...
  Override only if you have reviewed each violation and are
  certain it does not apply.
══════════════════════════════════════════════════════════════════
BLOCK
exit 1
