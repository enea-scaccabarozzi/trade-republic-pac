# LLM Semantic Review Hook

Git hook that runs Gemini-powered semantic review on commits, enforcing the project's coding standards beyond what classical linters catch.

## How It Works

Registered via the pre-commit framework as a `pre-commit` stage hook. Uses Gemini 2.5 Flash. Fails with violations; skip via `LLM_REVIEW_SKIP=1`.

Classical hooks (format, lint, typecheck) always run first. LLM review only runs if they pass.

## Review Agents

Each agent enforces a specific standard. Agents activate based on which files changed:

| Agent | Policy | Activates On |
|---|---|---|
| BDD | `policies/bdd.md` | Production Python code under `src/pac/` |
| Testing | `policies/testing.md` | Production or test Python code |
| Documentation | `policies/documentation.md` | Docs/READMEs or production Python code |
| Architecture | `policies/architecture.md` | Production Python code under `src/pac/` |
| Research | `policies/research.md` | Files under `research/` |

All activated agents run in parallel. Each agent receives the full staged diff and the commit message for context. The dashboard (`src/pac/backtester/dashboard/`) is excluded from all agents.

## Adding a New Agent

1. Create a policy file in `policies/<name>.md`
1. Add a path pattern in `review.sh` (in the agent routing section)
1. Add the agent name to `AGENT_ORDER` in `review.sh`

The policy must instruct the model to respond with `verdict: PASS` or `verdict: FAIL`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_REVIEW_MAX_FILES` | 40 | Block commit when diff exceeds this many files |
| `LLM_REVIEW_MAX_LINES` | 4000 | Block commit when diff exceeds this many lines |
| `LLM_REVIEW_TIMEOUT` | 90 | Timeout (seconds) per agent |
| `LLM_REVIEW_SKIP` | unset | Set to `1` to skip LLM review |

## Prerequisites

- Gemini CLI installed and authenticated (`gemini --version`)
- If Gemini is not available, the hook skips gracefully
