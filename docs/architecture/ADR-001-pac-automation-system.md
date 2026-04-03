# PAC Automation System Architecture

**Source:** Task 001 (April 2026)

## Decision

Build a containerized portfolio rebalancing assistant for Trade Republic using a Starlette ASGI app, with Protocol-based signal rules and Telegram webhook notifications.

## Why

- Automate detection of portfolio drift from a 70/15/15 target allocation (Stocks/Gold/Bonds)
- Never execute trades — all recommendations are advisory, acted on manually
- Lightweight container — runs on any Docker-compatible host (VPS, NAS, orchestrator)
- Extensible signal system so new rebalance rules can be added without modifying existing code

## Solution

### Data Flow

```
Scheduler (cron)
       │
       ▼ POST /jobs/hourly-check  or  /jobs/monthly-pac
┌──────────────────┐
│  Starlette ASGI  │──▶ tr_session() context manager ──▶ TR WebSocket API (pytr)
│  (Docker)        │           │
│                  │    PortfolioSnapshot
│                  │           │
│                  │    calculate_deviations() → DeviationReport
│                  │           │
│                  │    SignalRegistry.evaluate_all() → list[Signal]
│                  │           │
│                  │    send_signal_alert() / send_pac_notification()
│                  │           │
└──────────────────┘           ▼
       ▲               Telegram Bot API
       │
Telegram webhook (POST /webhook) ──▶ command handlers (/status, /portfolio, etc.)
```

### Key Design Choices

**On-demand job execution:** An external scheduler (cron, systemd timer, or orchestrator) sends HTTP POST requests to trigger jobs. TR WebSocket connections are opened per-request via `tr_session()` async context manager and closed after each job completes.

**Protocol-based signal rules:** `SignalRule` is a `typing.Protocol` (structural subtyping, not ABC). Rules are stateless — configuration comes from `Settings`. New rules plug in by implementing the protocol and registering in `SignalRegistry`.

**Webhook-based Telegram:** Instead of long-polling, Telegram delivers updates as HTTP POST to `/webhook`. Secret token validation via `X-Telegram-Bot-Api-Secret-Token` header. Scheduled jobs authenticated via `X-Job-Secret` header.

## Implementation Phases

| Phase          | What Changed                                                        |
| -------------- | ------------------------------------------------------------------- |
| 1. Scaffolding | Project structure, Pydantic models (Position, Signal, etc.), config |
| 2. TR Client   | Read-only `pytr` wrapper with typed async methods, cookie auth      |
| 3. Analysis    | Deviation calculation, PAC volume redistribution from bank balance  |
| 4. Signals     | Protocol-based rule system, threshold + cycle inversion rules       |
| 5. Telegram    | Bot command handlers, Markdown formatting, inline keyboards         |
| 6. Scheduler   | Starlette ASGI app, webhook endpoints, scheduled job endpoints      |
| 7. Deployment  | Dockerfile (multi-stage uv build), GitHub Actions CI/CD             |

## Key Architectural Patterns

### Signal Rule Protocol

```python
@runtime_checkable
class SignalRule(Protocol):
    @property
    def name(self) -> str: ...

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        settings: Settings,
    ) -> list[Signal]: ...
```

Rules are registered in `SignalRegistry` and evaluated together:

```python
registry = SignalRegistry()
registry.register(ThresholdDeviationRule())
registry.register(CycleInversionRule())
signals = registry.evaluate_all(report, snapshot, settings)
```

### Per-Request TR Connection

```python
@asynccontextmanager
async def tr_session(settings: Settings) -> AsyncIterator[TRClient]:
    client = TRClient(settings)
    await client.connect()
    try:
        yield client
    finally:
        await client.close()
```

### Starlette Endpoint Authentication

```python
async def hourly_check(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    expected = settings.job_secret
    received = request.headers.get("X-Job-Secret", "")
    if not hmac.compare_digest(expected, received):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    # ... evaluate signals
```

## Current Structure

```
src/pac/
├── __main__.py           # Structlog config + uvicorn runner
├── app.py                # Starlette ASGI app (webhook, job, health endpoints)
├── config.py             # Pydantic Settings (env vars with PAC_ prefix)
├── models/
│   ├── portfolio.py      # Position, PortfolioSnapshot, Allocation, AssetClass
│   └── signals.py        # Signal, RebalanceAction, SignalSeverity
├── tr/
│   ├── client.py         # TRClient wrapper + tr_session() context manager
│   └── exceptions.py     # TR-specific exceptions
├── analysis/
│   ├── deviation.py      # calculate_deviations() → DeviationReport
│   └── rebalance.py      # calculate_pac_plan() → PacPlan
├── signals/
│   ├── base.py           # SignalRule Protocol
│   ├── registry.py       # SignalRegistry + create_default_registry()
│   └── rules/
│       ├── threshold.py  # ThresholdDeviationRule
│       └── cycle.py      # CycleInversionRule
└── telegram/
    ├── bot.py            # PTB Application, command handlers
    ├── formatting.py     # Markdown message formatters
    └── keyboards.py      # Inline keyboard builders
```

## Deleted

- `hello.py` — placeholder from `uv init`
