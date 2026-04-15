# Crisis Strategy Research — Reproducibility Guide

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)

## Install Dependencies

```bash
uv sync --group backtest --group research
```

## Generate Figures

```bash
python research/papers/crisis-strategy/generate_figures.py
```

## Output

Figures are written to `research/papers/crisis-strategy/figures/`.
The script also prints all numerical claims from the paper for verification.

## Notes

- `matplotlib` is managed via the `research` dependency group (not installed ad-hoc).
- The script imports from `pac.backtester.data` and `pac.rules.builtin._indicators`
  for consistency with production code — this ensures the paper validates the
  *actual* production indicator math, not a reimplementation.
- Price data is cached to `~/.pac/cache/` (same as the backtester).
  Delete the cache directory to force a fresh fetch.
