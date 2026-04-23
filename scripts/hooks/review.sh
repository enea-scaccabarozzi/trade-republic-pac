#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Configuration (env var overrides) ---
MAX_FILES="${LLM_REVIEW_MAX_FILES:-40}"
MAX_LINES="${LLM_REVIEW_MAX_LINES:-3000}"
TIMEOUT_FLASH="${LLM_REVIEW_TIMEOUT_FLASH:-120}"
TIMEOUT_PRO="${LLM_REVIEW_TIMEOUT_PRO:-180}"
SKIP="${LLM_REVIEW_SKIP:-0}"

# --- Argument parsing ---
MODE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$MODE" != "commit" && "$MODE" != "push" ]]; then
  echo "Usage: review.sh --mode commit|push" >&2
  exit 1
fi

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

# --- Model selection ---
if [[ "$MODE" == "commit" ]]; then
  MODEL="gemini-2.5-flash"
  TIMEOUT="$TIMEOUT_FLASH"
else
  MODEL="gemini-2.5-pro"
  TIMEOUT="$TIMEOUT_PRO"
fi

# --- Relevant extensions filter ---
EXTENSIONS_PATTERN='\.py$|\.md$|\.feature$|\.toml$|\.yaml$|\.yml$'
DASHBOARD_EXCLUDE='src/pac/backtester/dashboard/'

# --- Compute diff ---
if [[ "$MODE" == "commit" ]]; then
  DIFF=$(git diff --cached --name-only | grep -E "$EXTENSIONS_PATTERN" | grep -v "$DASHBOARD_EXCLUDE" || true)
  DIFF_CONTENT=$(git diff --cached -- $(echo "$DIFF" | tr '\n' ' ') 2>/dev/null || true)
else
  BASE_BRANCH=$(git rev-parse --verify main 2>/dev/null || git rev-parse --verify master 2>/dev/null || echo "HEAD~10")
  DIFF=$(git diff "$BASE_BRANCH"...HEAD --name-only | grep -E "$EXTENSIONS_PATTERN" | grep -v "$DASHBOARD_EXCLUDE" || true)
  DIFF_CONTENT=$(git diff "$BASE_BRANCH"...HEAD -- $(echo "$DIFF" | tr '\n' ' ') 2>/dev/null || true)
fi

# --- No relevant files check ---
if [[ -z "$DIFF" ]]; then
  echo "LLM review: no reviewable changes."
  exit 0
fi

FILE_COUNT=$(echo "$DIFF" | wc -l | tr -d ' ')
LINE_COUNT=$(echo "$DIFF_CONTENT" | wc -l | tr -d ' ')

# --- Context overflow check ---
if [[ "$FILE_COUNT" -gt "$MAX_FILES" || "$LINE_COUNT" -gt "$MAX_LINES" ]]; then
  if [[ "$MODE" == "push" ]]; then
    cat >&2 <<'BLOCK'
══════════════════════════════════════════════════════════════════
  ⚠  CONTEXT LIMIT EXCEEDED
BLOCK
    echo "  ${FILE_COUNT} files changed, ~${LINE_COUNT} lines of diff." >&2
    cat >&2 <<'BLOCK'
  Reviews beyond this threshold produce incomplete analysis
  and silently miss violations.

  PUSH BLOCKED. Split your changes into smaller, focused
  commits and pushes before proceeding. A review of this
  size cannot be trusted.
══════════════════════════════════════════════════════════════════
BLOCK
    exit 1
  else
    cat >&2 <<'BLOCK'
══════════════════════════════════════════════════════════════════
  ⚠  CONTEXT LIMIT EXCEEDED
BLOCK
    echo "  ${FILE_COUNT} files changed, ~${LINE_COUNT} lines of diff." >&2
    cat >&2 <<'BLOCK'
  Reviews beyond this threshold produce incomplete analysis
  and silently miss violations.

  Split your changes into smaller, focused commits.
  Proceed with reduced review confidence? [y/N]
══════════════════════════════════════════════════════════════════
BLOCK
    read -r -n 1 OVERFLOW_REPLY </dev/tty 2>/dev/null || OVERFLOW_REPLY="n"
    echo >&2
    if [[ ! "$OVERFLOW_REPLY" =~ ^[Yy]$ ]]; then
      echo "LLM review: skipped (context limit exceeded)."
      exit 0
    fi
  fi
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
done <<< "$DIFF"

if [[ "$HAS_PRODUCTION_PY" == "true" ]]; then
  ACTIVATE_BDD=true
  ACTIVATE_TESTING=true
  ACTIVATE_DOCUMENTATION=true
  ACTIVATE_ARCHITECTURE=true
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
Review the following diff for violations.

Changed files:
${DIFF}

--- DIFF START ---
${DIFF_CONTENT}
--- DIFF END ---
PROMPT_EOF

  (
    gemini \
      -p "$(cat "$PROMPT_FILE")" \
      -m "$MODEL" \
      --admin-policy "$POLICY_FILE" \
      --output-format text \
      --yolo \
      2>/dev/null > "$OUTPUT_FILE" &
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

# --- Result parsing and output ---
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

  if echo "$CONTENT" | grep -qi "verdict: *PASS"; then
    PASSED=$((PASSED + 1))
  elif echo "$CONTENT" | grep -qi "verdict: *TIMEOUT"; then
    PASSED=$((PASSED + 1))
    echo "LLM review: ${agent} agent timed out (treated as pass)." >&2
  else
    FAILURES+=("$agent")
    FAILURE_OUTPUTS+=("$CONTENT")
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
  findings=$(echo "$output" | grep -vi "verdict:" || echo "$output")

  cat >&2 <<BLOCK

  ── ${label} ─────────────────────────────────────────────────
$(echo "$findings" | sed 's/^/  /')
BLOCK
done

if [[ "$MODE" == "commit" ]]; then
  cat >&2 <<'BLOCK'

  ────────────────────────────────────────────────────────────
  ACTION REQUIRED: Fix the violations above and recommit.
  Override only if you have reviewed each violation and are
  certain it does not apply. Ignoring valid findings degrades
  codebase quality for every future contributor.

  Commit anyway? [y/N]
══════════════════════════════════════════════════════════════════
BLOCK
  read -r -n 1 REPLY </dev/tty 2>/dev/null || REPLY="n"
  echo >&2
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    exit 0
  else
    exit 1
  fi
else
  cat >&2 <<'BLOCK'

  ────────────────────────────────────────────────────────────
  PUSH BLOCKED. Fix the violations above, recommit, and
  push again. This review is not optional — violations must
  be resolved before code reaches the remote.
══════════════════════════════════════════════════════════════════
BLOCK
  exit 1
fi
