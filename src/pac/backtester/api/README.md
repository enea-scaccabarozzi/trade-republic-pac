# Backtester API

FastAPI REST API for the backtester dashboard. Serves experiment metadata, saved run results, strategy snapshots, and supports triggering new backtest runs.

## Architectural Role

Depends on: [`backtester/results`](../results/), [`backtester/research`](../research/), [`config`](../../config/).
Consumed by: [`dashboard`](../dashboard/) (React frontend via HTTP).

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `backtester/results` | `pac.backtester.results` | Load and list saved backtest run results from the filesystem | `ResultStore`, `RunResult` |
| `backtester/research` | `pac.backtester.research` | Serve experiment metadata and papers from the research directory | `ExperimentManifest` |
| `config` | `pac.config` | Application settings required to locate data directories and validate requests | `Settings` |

## Key Components

| Component | File | Purpose |
|---|---|---|
| `create_app()` | `app.py` | FastAPI app factory with all routes and middleware registered |
| `BacktestManager` | `deps.py` | FastAPI dependency providing `ResultStore` and config to route handlers |
| Research routes | `routes/research.py` | `GET /api/research/experiments`, `/papers`, `/strategies` |
| Run routes | `routes/runs.py` | `GET /api/runs`, `GET /api/runs/{id}` |
| Strategy routes | `routes/strategies.py` | `GET /api/strategies` (available strategy names) |

## Configuration

The API reads the same `pac.yaml` as the main app. Results are served from `.pac/backtests/`. Research artifacts are served from the `research/` directory at the repo root.

## Usage

```bash
just dashboard          # starts both the FastAPI backend and the React frontend
just dashboard --port 9000  # custom port
```

## Commands

```bash
just test -k test_research_routes    # research API route tests
just test -k backtester              # all backtester tests
```

## See Also

- [Dashboard](../dashboard/) — React frontend that consumes this API
- [Results](../results/) — `RunResult` JSON schema and `ResultStore`
- [Research](../research/) — `ExperimentManifest` and experiment metadata
