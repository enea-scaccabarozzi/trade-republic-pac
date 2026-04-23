# LLM Semantic Review Hooks

Git hooks that run Gemini-powered semantic reviews on commits and pushes, enforcing the project's coding standards beyond what classical linters catch.

## How It Works

Two git hooks are registered via the pre-commit framework:

| Hook | Trigger | Model | Behavior |
|---|---|---|---|
| `llm-review-commit` | pre-commit | Gemini 2.5 Flash | Advisory — prompts to fix violations, default is to abort |
| `llm-review-push` | pre-push | Gemini 2.5 Pro | Blocking — push fails on any violation |

Classical hooks (format, lint, typecheck, tests) always run first. LLM review only runs if they pass.

## Review Agents

Each agent enforces a specific standard. Agents activate based on which files changed:

| Agent | Policy | Activates On |
|---|---|---|
| BDD | `policies/bdd.md` | Production Python code under `src/pac/` |
| Testing | `policies/testing.md` | Production or test Python code |
| Documentation | `policies/documentation.md` | Python code, docs, or READMEs |
| Architecture | `policies/architecture.md` | Production Python code under `src/pac/` |
| Research | `policies/research.md` | Files under `research/` |

All activated agents run in parallel. The dashboard (`src/pac/backtester/dashboard/`) is excluded from all agents.

## Adding a New Agent

1. Create a policy file in `policies/<name>.md`
2. Add a path pattern in `review.sh` (in the agent routing section)
3. Add the agent name to `AGENT_ORDER` in `review.sh`

The policy must instruct the model to respond with `verdict: PASS` or `verdict: FAIL`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_REVIEW_MAX_FILES` | 40 | Warn when diff exceeds this many files |
| `LLM_REVIEW_MAX_LINES` | 3000 | Warn when diff exceeds this many lines |
| `LLM_REVIEW_SKIP` | unset | Set to `1` to skip LLM review |
| `LLM_REVIEW_TIMEOUT_FLASH` | 60 | Timeout (seconds) for Flash agents |
| `LLM_REVIEW_TIMEOUT_PRO` | 120 | Timeout (seconds) for Pro agents |

## Prerequisites

- Gemini CLI installed and authenticated (`gemini --version`)
- If Gemini is not available, hooks skip gracefully
