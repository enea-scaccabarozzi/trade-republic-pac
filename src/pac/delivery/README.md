# Delivery

Channel abstraction and message routing. Defines the `DeliveryChannel` base class and auto-discovers concrete channel implementations from the `channels/` subpackages.

## Architectural Role

| Aspect      | Details                                                                                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Depends on  | [`models`](../models/) (`SignalSeverity`, `PortfolioSnapshot`), [`analysis`](../analysis/) (deviation and PAC plan data), [`tr`](../tr/) (Telegram error handling) |
| Consumed by | [`orchestrator`](../orchestrator/) (wires channels, calls `send()`), [`templates`](../templates/) (produces `RenderedMessage`)        |
| Boundary    | Channel abstraction, message delivery, channel-specific interactive features                                                          |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `models` | `pac.models` | Signal severity and portfolio data used by core `DeliveryChannel` and Telegram formatting | `SignalSeverity`, `PortfolioSnapshot` |
| `analysis` | `pac.analysis` | Deviation and PAC plan data formatted and displayed by Telegram channel | `DeviationReport`, `PacPlan` |
| `tr` | `pac.tr` | Exception handling for Trade Republic API errors in Telegram error responses | `TRClientError`, `TRConnectionError`, etc. |

## Key Components

| Component                  | File                              | Description                                                   |
| -------------------------- | --------------------------------- | ------------------------------------------------------------- |
| `DeliveryChannel[ConfigT]` | `base.py`                         | ABC + Generic base class; `__init_subclass__` extracts config |
| `RenderedMessage`          | `base.py`                         | Channel-agnostic output model (`content`, `format`, severity) |
| `discover_channels()`      | `discovery.py`                    | Scans `channels/` subpackages for concrete implementations    |
| `TelegramChannel`          | `channels/telegram/channel.py`    | PTB-based message delivery with lifecycle hooks               |
| `create_bot_from_app`      | `channels/telegram/bot.py`        | PTB `Application` factory with interactive command handlers   |
| Formatting functions       | `channels/telegram/formatting.py` | MarkdownV2 formatters for portfolio, signals, and PAC plan    |
| Keyboard builders          | `channels/telegram/keyboards.py`  | Telegram inline keyboard builders                             |

## Configuration

Channel config is defined per-channel in `pac.yaml` under the `channels:` key. Each channel type declares a Pydantic config model via its `Generic[ConfigT]` type argument — raw YAML values are validated against this model in `Orchestrator.from_settings()`.

## Usage

```python
from pac.delivery import DeliveryChannel, RenderedMessage, discover_channels

# Discovery — returns {name: class} mapping
channels = discover_channels()

# Instantiate with validated config
channel = channels["telegram"](typed_config)

# Lifecycle
await channel.set_orchestrator(orchestrator)
await channel.start()
await channel.send(rendered_message)
await channel.stop()
```

### Adding a Channel

```bash
just new-channel my_channel
```

Subclass `DeliveryChannel[YourConfig]`, implement `name`, `supported_formats`, and `send()`, then place it in `channels/<name>/channel.py`. Discovery is automatic.

## Commands

```bash
just test -k test_telegram              # Telegram channel tests
just test -k test_channel_discovery     # discovery unit tests
just test -k test_channel_discovery_bdd # discovery BDD scenarios
just test -k test_telegram_delivery_bdd # Telegram delivery BDD scenarios
just test -k test_formatting            # formatting function tests
```

## See Also

- [Templates](../templates/) — produces `RenderedMessage` consumed by channels
- [Orchestrator](../orchestrator/) — wires channels and calls `send()`
- [ADR-002: Extensible Architecture](../../../docs/architecture/ADR-002-extensible-architecture.md) — channel design rationale
