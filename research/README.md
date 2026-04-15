# Research

Structured research workflow for iterative strategy development and validation.

## Workflow

The research workflow has four phases. Enter at any phase; skip what doesn't apply.

```
① EXPLORE          ② VALIDATE           ③ HARDEN            ④ PUBLISH
─────────          ──────────           ────────            ─────────
Marimo notebook    Script/notebook      Framework run       Paper +
Free-form code     Custom indicators    Real strategy       Figures
Tulipy + ad-hoc    Quick-test (N=1)     Param sweeps        Full MC
Form hypothesis    Compare variants     OOS validation      Archive
                   Accept / reject      Dashboard viz
                                        Quantstats reports
                                        Save stable runs
```

Artifacts are persisted at every phase. Nothing lives in `/tmp/`.

## Directory Structure

```
research/
├── experiments/           # One subdirectory per experiment
│   ├── _template/         # Scaffold template (not an experiment)
│   ├── 001-my-idea/       # Auto-numbered experiment
│   │   ├── experiment.toml
│   │   ├── explore.py     # Marimo notebook
│   │   ├── results/       # Result files (.json, .csv)
│   │   └── reports/       # Generated HTML reports (gitignored)
│   └── 002-another-idea/
├── papers/                # Published research papers
└── strategies/            # Shared strategy configurations
```

## `experiment.toml` Schema

Each experiment has a seed manifest (`experiment.toml`) with immutable metadata.
Status and artifacts are **auto-computed** from directory contents — never set manually
(unless you want to force a status like `"rejected"`).

### Required Fields

| Field        | Type        | Description                                  |
| ------------ | ----------- | -------------------------------------------- |
| `id`         | `string`    | Zero-padded 3-digit ID (e.g., `"001"`)       |
| `slug`       | `string`    | Hyphenated name (e.g., `"crisis-timing"`)    |
| `title`      | `string`    | Human-readable title                         |
| `hypothesis` | `string`    | What you're testing (fill in after scaffold) |
| `created`    | `date`      | TOML bare date (e.g., `2026-04-13`)          |
| `tags`       | `list[str]` | Categorization tags                          |

### Optional Fields

| Field                   | Type     | Description                          |
| ----------------------- | -------- | ------------------------------------ |
| `status`                | `string` | Manual override (e.g., `"rejected"`) |
| `[experiment.strategy]` | table    | Strategy configuration               |
| `strategy.name`         | `string` | Strategy name                        |
| `strategy.params_file`  | `string` | Path to strategy parameters YAML     |

## Auto-Computed Status

Status is derived from directory contents:

1. **Manual override** — if `status` is set in `experiment.toml`, it wins
2. **`"validated"`** — if `results/` contains `.json` or `.csv` files
3. **`"exploring"`** — default (no results yet)

## Quick Start

```bash
# Create a new experiment
just new-experiment crisis_timing --title "Crisis Timing Asymmetry"

# Open the Marimo notebook
marimo edit research/experiments/001-crisis-timing/explore.py
```

## Conventions

- Experiment IDs are auto-incremented (001, 002, ...) by the scaffold script
- Marimo notebooks use `.py` format for version control compatibility
- Generated HTML reports (`reports/*.html`) are **not** committed to git
- `ResearchContext` API will be available after Phase 3 — for now, use direct imports
