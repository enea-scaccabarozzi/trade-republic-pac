# Orchestrator

Framework-agnostic signal dispatch pipeline. Wires config, rules, templates, and delivery channels into a single coordinator consumed by the HTTP adapter (`app.py`) and interactive channel handlers.

## Architectural Role

| Aspect      | Details                                                                                                                                                                                                                                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Depends on  | [`config`](../config/) (`Settings`), [`rules`](../rules/) (`SignalRegistry`), [`templates`](../templates/) (`TemplateEngine`, `FormatAdapter`), [`delivery`](../delivery/) (`DeliveryChannel`), [`analysis`](../analysis/) (`calculate_deviations`, `compute_pac_plan`), [`tr`](../tr/) (`tr_session`) |
| Consumed by | [`app.py`](../app.py) (HTTP adapter), interactive channel handlers (e.g. Telegram `/rebalance`)                                                                                                                                                                                                        |
| Boundary    | Signal dispatch coordination, lifecycle management, config-to-component wiring                                                                                                                                                                                                                         |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `analysis` | `pac.analysis` | Deviation calculation and PAC plan computation for signal evaluation | `DeviationReport`, `calculate_deviations`, `compute_pac_plan` |
| `config` | `pac.config` | Application settings required to wire rules, channels, and templates at startup | `Settings` |
| `delivery` | `pac.delivery` | Channel abstraction for routing rendered messages to Telegram and other targets | `DeliveryChannel`, `discover_channels` |
| `models` | `pac.models` | Shared portfolio and signal types passed through the dispatch pipeline | `PortfolioSnapshot`, `Signal` |
| `rules` | `pac.rules` | Signal rule registry and evaluation — core of the dispatch pipeline | `SignalRegistry`, `discover_rules` |
| `templates` | `pac.templates` | Jinja2 rendering engine that converts signal data into formatted messages | `TemplateEngine`, `FormatAdapter` |
| `tr` | `pac.tr` | WebSocket client for fetching live portfolio data on each signal evaluation | `tr_session` |

## Key Components

| Component                | File              | Description                                                          |
| ------------------------ | ----------------- | -------------------------------------------------------------------- |
| `Orchestrator`           | `orchestrator.py` | Central coordinator — holds registry, channels, engine, and adapters |
| `from_settings()`        | `orchestrator.py` | Factory: discovers rules/channels, validates config cross-references |
| `dispatch_signal()`      | `orchestrator.py` | Full pipeline: fetch portfolio → evaluate → render → send            |
| `evaluate_signal()`      | `orchestrator.py` | Evaluate-only (no send) — used by interactive handlers               |
| `get_portfolio_status()` | `orchestrator.py` | Fetch portfolio + compute deviations — used by `/status`             |
| `compute_pac_plan()`     | `orchestrator.py` | PAC redistribution from signal params — used by `/redistribute`      |
| `DispatchResult`         | `orchestrator.py` | Pydantic result model: `signal_name`, `signal_count`, `delivered`    |
| `SignalNotFoundError`    | `orchestrator.py` | Raised when signal name is not in config                             |

## Configuration

`Orchestrator.from_settings()` performs cross-validation at construction time (no network calls):

1. Discovers rules via `discover_rules()` and registers them in `SignalRegistry`
2. Discovers channels via `discover_channels()` and instantiates with typed config
3. Builds a `TemplateEngine` and discovers `FormatAdapter` subclasses
4. Validates every signal config references a known rule, channel(s), and template
5. Cross-validates that each channel's `supported_formats` has a matching adapter

## Usage

```python
from pac.config import load_config
from pac.orchestrator import Orchestrator

settings = load_config()
orch = Orchestrator.from_settings(settings)

# Lifecycle
await orch.start()

# Full pipeline — evaluate + render + send
result = await orch.dispatch_signal("threshold_check")
result.delivered  # True if signals were sent

# Evaluate-only (for interactive handlers)
signals = await orch.evaluate_signal("threshold_check")

# Portfolio status
snapshot, report = await orch.get_portfolio_status()

await orch.stop()
```

## Commands

```bash
just test -k test_orchestrator        # orchestrator unit tests
just test -k test_config_wiring_bdd   # config wiring BDD scenarios
just test -k test_signal_dispatch_bdd # signal dispatch BDD scenarios
```

## See Also

- [Config](../config/) — `Settings` consumed by `from_settings()`
- [Rules](../rules/) — `SignalRegistry` evaluates signals
- [Templates](../templates/) — `TemplateEngine` renders messages
- [Delivery](../delivery/) — channels receive rendered messages
- [ADR-002: Extensible Architecture](../../../docs/architecture/ADR-002-extensible-architecture.md) — dispatch pipeline design
