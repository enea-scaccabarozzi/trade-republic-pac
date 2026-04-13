# React Dashboard — Strategy Validation Workbench

**Source:** Task 011 (April 2026)
**Status:** Accepted

## Decision

Replace the legacy NiceGUI server-rendered dashboard with a React SPA backed by a FastAPI REST API, redesigning it from a data viewer into a strategy validation workbench with indicator overlays, signal analysis, and a clone-and-tweak workflow.

## Why

- The NiceGUI dashboard was a quick read-only data viewer — it could not support interactive workflows like parameter tweaking, multi-run comparison, or signal drill-down
- Server-rendered UI created tight coupling between Python state and frontend rendering, making the UI difficult to extend
- Strategy developers need to iterate rapidly: clone a run, tweak params, compare results — this requires a rich client-side experience
- Signal and indicator data was discarded during simulation, preventing post-hoc analysis of *why* strategies behaved as they did
- A REST API decouples data access from presentation, enabling future clients (CLI rich output, notebooks, CI)

## Problem Statement

The backtester produced `RunResult` objects with final metrics but discarded intermediate data (signal triggers, indicator snapshots, strategy events). The NiceGUI dashboard could show charts and metrics but offered no way to:

- Understand when/why signals fired
- See how each rule influenced outcomes
- Compare multiple runs side-by-side with overlaid indicators
- Quickly iterate on parameters (clone → tweak → compare)

## Solution

### Before

NiceGUI server-rendered dashboard (`src/pac/backtester/dashboard/`) with Python-driven UI, Plotly charts rendered server-side, and tightly coupled state management. No API layer — all data access was inline Python.

### After

Three-layer architecture:

1. **Data Enrichment** — Extensible indicator/event capture system in the simulation engine (signal logs, strategy events, indicator snapshots via `IndicatorProvider` registry + weekly sampling, benchmark equity curve, per-iteration metric distributions)
2. **FastAPI REST API** (`src/pac/backtester/api/`) — Stateless endpoints over `ResultStore` and `run_pipeline()`, SSE progress streaming for in-progress backtests
3. **React SPA** (`src/pac/backtester/dashboard/`) — Vite + React 19 + Tailwind v4 + shadcn/ui, served as static files mounted by the API

## Implementation Phases

| Phase | What Changed |
| --- | --- |
| 1. Data Enrichment | Extensible indicator/event capture system, benchmark equity curve, per-iteration metric distributions |
| 2. API Backend | FastAPI REST endpoints (`/api/runs`, `/api/strategies`), SSE progress streaming, dependency injection |
| 3. SPA Scaffold | Vite + React + Tailwind + shadcn/ui + TanStack Router, sidebar layout, theme system, shared component library |
| 4. Dashboard Home | Portfolio-level overview, sortable results table, batch actions (compare, delete) |
| 5. Run Detail — Overview & Charts | Tabbed detail view, KPI cards, equity/allocation/drawdown charts with brush zoom, overlay system |
| 6. Signals & Trades | Signal activity log, rule summary table, strategy event timeline, trade table with virtual scrolling |
| 7. Run Wizard | Multi-step form, dynamic strategy params from JSON schema, SSE progress, clone-and-tweak flow |
| 8. Compare View | Multi-run overlay charts, metrics radar, side-by-side metrics table, signal activity heatmap |
| 9. Polish & CLI | CLI update, Justfile integration, production build, responsive polish |

## Key Architectural Patterns

### 1. API Layer — FastAPI with Dependency Injection

Stateless REST endpoints delegate to `ResultStore` and `run_pipeline()`. Dependencies are injected via FastAPI's `Depends()`:

```python
# src/pac/backtester/api/routes/runs.py
@router.get("/runs")
async def list_runs(store: ResultStore = Depends(get_store)) -> list[RunSummary]:
    ...

@router.post("/runs")
async def start_run(config: RunConfig, store: ResultStore = Depends(get_store)) -> RunStarted:
    ...

@router.get("/runs/{run_id}/progress")
async def run_progress(run_id: str) -> EventSourceResponse:
    # SSE stream for real-time progress updates
    ...
```

### 2. Indicator Overlay System — Togglable Layers on Charts

Indicators are not standalone panels. They render as optional overlays on existing charts (equity, allocation, drawdown). Each chart has a "Layers" toggle that lists compatible overlays:

- Boolean indicators → colored background spans
- Continuous indicators → secondary Y-axis lines
- Strategy events → vertical marker lines with tooltips
- Signal triggers → dot markers on the timeline

Overlay visibility is persisted in Zustand → localStorage.

### 3. Shared Component Library

All repeated UI elements are shared components in `src/components/`. Phases declare which components they introduce and which they reuse:

- `kpi-card.tsx` — metric display with trend indicator and confidence interval
- `chart-container.tsx` — wrapper with overlay panel, brush zoom, and loading state
- `data-table.tsx` / `virtual-data-table.tsx` — TanStack Table with column visibility toggle
- `stat-badge.tsx`, `metric-formatter.tsx`, `confidence-value.tsx` — consistent number formatting
- `empty-state.tsx`, `loading-skeleton.tsx` — standard placeholder states

## Current Structure

```
src/pac/backtester/api/
├── app.py               # FastAPI application, mounts SPA static files
├── deps.py              # Dependency injection (ResultStore, config)
├── models.py            # API request/response models
└── routes/
    ├── runs.py           # CRUD + SSE progress for backtest runs
    └── strategies.py     # Available strategies + JSON schemas

src/pac/backtester/dashboard/
├── vite.config.ts        # Vite build config with API proxy
├── biome.json            # Lint/format (replaces ESLint+Prettier)
├── package.json          # Bun-managed dependencies
└── src/
    ├── components/       # Shared component library (see above)
    │   ├── ui/           # shadcn/ui primitives
    │   ├── charts/       # Chart-specific components
    │   ├── compare/      # Compare view components
    │   ├── dashboard/    # Dashboard home components
    │   ├── run-detail/   # Run detail tab components
    │   └── wizard/       # Run wizard step components
    ├── hooks/            # TanStack Query hooks, custom hooks
    ├── routes/           # TanStack Router file-based routes
    ├── stores/           # Zustand stores (compare selections, overlay preferences)
    ├── types/            # Shared TypeScript types
    └── lib/              # Utilities, API client
```

## Deleted

- `src/pac/backtester/dashboard.legacy/` — NiceGUI dashboard (moved aside, preserved as `.legacy`)

## Technology Choices

| Layer | Technology | Rationale |
| --- | --- | --- |
| Build | Vite + React 19 | Fast HMR, modern React features |
| Styling | Tailwind CSS v4 + shadcn/ui | Utility-first with consistent design system |
| Charts | Recharts (via shadcn wrappers) | React-native charting with composable API |
| Tables | TanStack Table | Headless, virtual scrolling, column visibility |
| Routing | TanStack Router | Type-safe file-based routing |
| Forms | TanStack Form + Zod | Schema-driven validation, dynamic form generation |
| Server state | TanStack Query | Cache management, background refetch, SSE integration |
| Client state | Zustand | Lightweight, persisted to localStorage |
| Lint/Format | Biome | Single tool replaces ESLint + Prettier |
| Package mgr | Bun | Fast installs, native TypeScript execution |
