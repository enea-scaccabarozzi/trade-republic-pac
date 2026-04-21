# Templates

Format-agnostic message rendering via Jinja2 `SandboxedEnvironment` and pluggable format adapters. Templates call formatting functions (`bold()`, `escape()`, etc.) without knowing the target channel.

## Architectural Role

| Aspect      | Details                                                                                   |
| ----------- | ----------------------------------------------------------------------------------------- |
| Depends on  | [`delivery`](../delivery/) (`RenderedMessage`), [`models`](../models/) (`SignalSeverity`) |
| Consumed by | [`orchestrator`](../orchestrator/) (calls `render()` in the dispatch pipeline)            |
| Boundary    | Template loading, adapter-injected formatting, rendered message production                |

## Dependencies

> Exported items listed below are representative — other exports from each module may also be imported.

| Module | Import Path | Why Required | Representative Exports |
|---|---|---|---|
| `delivery` | `pac.delivery` | `RenderedMessage` is the output type of `TemplateEngine.render()` — owned by the delivery layer | `RenderedMessage` |
| `models` | `pac.models` | Signal severity used to classify templates by urgency level | `SignalSeverity` |

## Key Components

| Component           | File                      | Description                                                              |
| ------------------- | ------------------------- | ------------------------------------------------------------------------ |
| `TemplateEngine`    | `engine.py`               | Loads `.j2` templates, injects adapter methods as Jinja2 globals         |
| `FormatAdapter`     | `adapters/base.py`        | ABC defining the formatting contract (`bold`, `escape`, `literal`, etc.) |
| `MarkdownV2Adapter` | `adapters/markdown_v2.py` | Telegram MarkdownV2 escaping and formatting                              |
| `PlainTextAdapter`  | `adapters/plain_text.py`  | No-markup plain-text fallback                                            |

### Built-in Templates

| Template         | File                          | Expected Data                     |
| ---------------- | ----------------------------- | --------------------------------- |
| Threshold alert  | `builtin/threshold_alert.j2`  | `signal`, `deviations` (optional) |
| Cycle alert      | `builtin/cycle_alert.j2`      | `signal`                          |
| PAC plan         | `builtin/pac_plan.j2`         | `plan`                            |
| Portfolio status | `builtin/portfolio_status.j2` | `deviations`, `snapshot`          |

## Configuration

`TemplateEngine` loads templates from a directory (default: `builtin/`). Custom filters are registered at init:

| Filter      | Purpose                            | Example Output |
| ----------- | ---------------------------------- | -------------- |
| `datefmt`   | Format `datetime` objects          | `2026-04-04`   |
| `numberfmt` | Format numbers to N decimal places | `70.15`        |
| `pctfmt`    | Percentage string                  | `70.0%`        |
| `eurfmt`    | Euro currency string               | `€500.00`      |

Data keys must not shadow reserved adapter method names (`bold`, `escape`, `literal`, etc.) — the engine raises `ValueError` on collision.

## Usage

```python
from pac.templates import TemplateEngine, MarkdownV2Adapter

engine = TemplateEngine()
adapter = MarkdownV2Adapter()

msg = engine.render(
    "threshold_alert",
    {"signal": signal, "deviations": deviations},
    adapter,
    signal_name="threshold_check",
    severity=signal.severity,
)
# msg is a RenderedMessage ready for DeliveryChannel.send()
```

### Adding an Adapter

Subclass `FormatAdapter`, implement all abstract methods (`escape`, `literal`, `bold`, `italic`, `code`, `code_block`, `link`, `heading`, `list_item`, `separator`), and pass the instance to `TemplateEngine.render()`. No registration or discovery required.

## Commands

```bash
just test -k test_engine                   # engine unit tests
just test -k test_adapters                 # adapter unit tests
just test -k test_template_rendering_bdd   # rendering BDD scenarios
just test -k test_format_adapters_bdd      # adapter BDD scenarios
```

## See Also

- [Delivery](../delivery/) — channels consume `RenderedMessage` via `send()`
- [Orchestrator](../orchestrator/) — calls `render()` in the dispatch pipeline
- [Rules](../rules/) — `build_template_data()` produces template context
- [ADR-002: Extensible Architecture](../../../docs/architecture/ADR-002-extensible-architecture.md) — template design rationale
