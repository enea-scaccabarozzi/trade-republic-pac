# Dashboard

Interactive web UI for exploring backtest results, configuring runs, and comparing strategies.
Built with [NiceGUI](https://nicegui.io/) (Quasar/Vue3 frontend, Python backend).

## Architectural Role

| Aspect      | Details                                                                                                                            |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Depends on  | [`results`](../results/) (ResultStore, RunResult), [`runner`](../runner.py) (pipeline), [`strategies`](../strategies/) (discovery) |
| Consumed by | CLI (`just dashboard`), standalone (`python -m pac.backtester.dashboard`)                                                          |
| Boundary    | Filesystem (`.pac/backtests/` read/write), HTTP (NiceGUI on localhost)                                                             |

## Key Components

| Component            | File                     | Purpose                                                                     |
| -------------------- | ------------------------ | --------------------------------------------------------------------------- |
| `start()`            | `app.py`                 | NiceGUI server lifecycle                                                    |
| `DashboardState`     | `state.py`               | ResultStore wrapper with in-memory cache                                    |
| `render_layout`      | `components/layout.py`   | Shared header + sidebar + theme toggle                                      |
| `results_list_page`  | `pages/results_list.py`  | Run listing at `/`                                                          |
| `result_detail_page` | `pages/result_detail.py` | Single run viewer at `/results/{id}`                                        |
| `run_page`           | `pages/run.py`           | Backtest configuration wizard at `/run`                                     |
| `compare_page`       | `pages/compare.py`       | Multi-run comparison at `/compare`                                          |
| Chart builders       | `charts.py`              | Plotly figure factories (equity, allocation, drawdown, overlay, comparison) |

## Pages

### Results List (`/`)
Displays all saved backtest runs in a sortable table. Supports multi-select for comparison, per-row "View" button for detail navigation.

### Result Detail (`/results/{run_id}`)
Interactive viewer for a single run: config summary, KPI cards, equity curve with confidence bands, allocation area chart, drawdown chart, metrics comparison table, filterable trade log (AG Grid).

### Run Backtest (`/run`)
Web form to configure and launch backtests. Strategy selection with dynamic param fields, live progress bar during Monte Carlo simulation, auto-redirect to results on completion.

### Compare (`/compare?runs=id1,id2,...`)
Side-by-side comparison: overlaid equity curves (with optional P5/P95 bands), metrics comparison table with best-performer highlighting, summary KPI cards, per-run allocation tabs.

## Getting Started

Install dashboard dependencies:

    uv sync --group dashboard

Start the dashboard:

    # Via Justfile
    just dashboard

    # Via CLI
    python -m pac.backtester.dashboard

    # Via backtester CLI
    python -m pac.backtester dashboard

    # With options
    just dashboard --port 9000 --reload

Open http://127.0.0.1:8090 in your browser.

## Development

Hot-reload for development:

    just dashboard --reload

### Key Commands

- `just dashboard` — start the dashboard server
- `just dashboard-sync` — install dashboard dependencies
- `just test -k test_state` — run state management tests
- `just test -k test_charts` — run chart builder tests
- `just test -k test_dashboard_navigation_bdd` — run BDD navigation scenarios
- `just test -k test_results_viewer_bdd` — run BDD results viewer scenarios
- `just test -k test_backtest_wizard_bdd` — run BDD wizard scenarios
- `just test -k test_compare_view_bdd` — run BDD compare view scenarios
- `just test src/pac/backtester/dashboard` — run all dashboard tests

## Architecture

### Data Flow

```
User (Browser)
  │
  ▼ NiceGUI (WebSocket)
Pages (results_list, result_detail, run, compare)
  │
  ├── DashboardState ← ResultStore (read .pac/backtests/*.json)
  ├── charts.py ← Plotly figure builders
  └── runner.py ← run_pipeline() for backtest execution
```

### Dependency Isolation

The dashboard is an optional module with its own dependency group (`dashboard = ["nicegui>=2.0", "plotly>=6.0"]`). Zero imports from the main `pac` app server. All imports gated behind try/except at entry points.

## See Also

- [Backtester README](../README.md)
- [Results module](../results/README.md)
- [ADR-005: Backtester Module](../../../docs/architecture/ADR-005-backtester-module.md)
