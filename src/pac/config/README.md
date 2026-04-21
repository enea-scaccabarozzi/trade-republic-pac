# Config

Configuration subsystem — loads and validates application settings from a YAML file (`pac.yaml`) with `${ENV_VAR}` interpolation for secrets.

## Architectural Role

| Aspect      | Details                                                                                                                                                 |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Depends on  | None (foundation layer)                                                                                                                                 |
| Consumed by | All other submodules — [`analysis`](../analysis/), [`rules`](../rules/), [`delivery`](../delivery/), [`orchestrator`](../orchestrator/), [`tr`](../tr/) |
| Boundary    | YAML loading, env var interpolation, Pydantic validation                                                                                                |

## Dependencies

This module has no internal `pac` imports — it is the foundation layer. Config models and the loader depend only on `pydantic` and `pyyaml` (external libraries).

## Key Components

| Component       | File        | Description                                                        |
| --------------- | ----------- | ------------------------------------------------------------------ |
| `Settings`      | `models.py` | Top-level Pydantic model aggregating all config sections           |
| `AppConfig`     | `models.py` | Application-level settings (log level, dev mode, port, job secret) |
| `BrokerConfig`  | `models.py` | Trade Republic connection credentials and cookie path              |
| `AssetConfig`   | `models.py` | Single asset definition (id, name, ISIN, target pct)               |
| `SignalConfig`  | `models.py` | Signal rule wiring: rule type, params, template, channels          |
| `load_config()` | `loader.py` | Loads YAML, interpolates `${ENV_VAR}`, validates via Pydantic      |

## Configuration

Config file resolution order:

1. Explicit `path` argument to `load_config()`
2. `PAC_CONFIG_PATH` environment variable
3. `pac.yaml` in the current working directory

Secrets use `${ENV_VAR}` interpolation — the loader substitutes env var values before Pydantic validation. See [`pac.yaml.example`](../../../pac.yaml.example) for the full schema.

### Validation Rules

`Settings` validates at load time:

- Asset target percentages sum to exactly 100%
- Asset IDs are unique
- Signal channel references point to configured channels

Signal-to-rule and signal-to-template cross-validation happens later in `Orchestrator.from_settings()`, after rules and templates are discovered.

### Computed Properties

| Property             | Returns                  | Description                     |
| -------------------- | ------------------------ | ------------------------------- |
| `asset_map`          | `dict[str, AssetConfig]` | Lookup asset config by ID       |
| `isin_to_asset_id`   | `dict[str, str]`         | Reverse lookup: ISIN → asset ID |
| `target_allocations` | `dict[str, Decimal]`     | Asset ID → target percentage    |

## Usage

```python
from pathlib import Path
from pac.config import load_config

settings = load_config()                            # pac.yaml in CWD
settings = load_config(Path("/etc/pac/pac.yaml"))   # explicit path

settings.broker.phone_number    # typed access
settings.app.job_secret         # HMAC secret for job auth
settings.target_allocations     # {asset_id: Decimal}
settings.isin_to_asset_id       # {isin: asset_id}
```

## Commands

```bash
just test -k test_loader              # loader unit tests
just test -k test_models              # model validation tests
just test -k test_config_loading_bdd  # BDD scenarios
just validate-config                  # validate pac.yaml against schema
```

## See Also

- [`pac.yaml.example`](../../../pac.yaml.example) — config schema reference
- [ADR-002: Extensible Architecture](../../../docs/architecture/ADR-002-extensible-architecture.md) — config design rationale
- [Orchestrator](../orchestrator/) — `from_settings()` wires config to rules, channels, and templates
