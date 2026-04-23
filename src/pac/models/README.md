# Models

Shared Pydantic domain models — portfolio snapshots, positions, allocations, signal types, and rebalance actions.

## Architectural Role

| Aspect | Details |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Depends on | None (foundation layer — no internal `pac` imports) |
| Consumed by | All other submodules — [`analysis`](../analysis/), [`rules`](../rules/), [`delivery`](../delivery/), [`templates`](../templates/), [`orchestrator`](../orchestrator/), [`tr`](../tr/) |
| Boundary | Domain data structures only — no I/O, no business logic |

## Dependencies

This module has no internal `pac` imports — it is the foundation layer. All other modules depend on it; it depends on none of them.

## Key Components

| Component | File | Description |
| ------------------- | -------------- | ------------------------------------------------------------------------------- |
| `Position` | `portfolio.py` | Single portfolio position (ISIN, name, quantity, price, market value, asset ID) |
| `Allocation` | `portfolio.py` | Actual vs target percentage for a single asset class |
| `PortfolioSnapshot` | `portfolio.py` | Point-in-time portfolio state with positions, cash, and computed `total_value` |
| `SavingsPlan` | `portfolio.py` | A configured savings plan (PAC) with ISIN, amount, and interval |
| `SignalSeverity` | `signals.py` | `StrEnum`: `INFO`, `WARNING`, `CRITICAL` |
| `ActionType` | `signals.py` | `StrEnum`: `BUY`, `SELL`, `HOLD` |
| `Signal` | `signals.py` | Alert produced by a signal rule (name, severity, message, metadata) |
| `RebalanceAction` | `signals.py` | Recommended buy/sell/hold action for an asset |

## Usage

```python
from datetime import UTC, datetime
from decimal import Decimal
from pac.models import PortfolioSnapshot, Position, Signal, SignalSeverity

snapshot = PortfolioSnapshot(
    positions=[
        Position(
            isin="IE00BK5BQT80", name="Vanguard FTSE All-World",
            quantity=Decimal("10"), price=Decimal("100.00"),
            market_value=Decimal("1000.00"), asset_id="stocks",
        ),
    ],
    cash=Decimal("200.00"),
    timestamp=datetime.now(UTC),
)

snapshot.total_value                          # Decimal("1200.00") — computed field
snapshot.allocations(["stocks", "gold"])      # {asset_id: Allocation}

signal = Signal(
    name="threshold_alert",
    severity=SignalSeverity.WARNING,
    message="Stocks deviation exceeds threshold",
    triggered_at=datetime.now(UTC),
)
```

### `PortfolioSnapshot` Computed Fields

| Field/Method | Returns | Description |
| --------------- | ----------------------- | ------------------------------------------- |
| `total_value` | `Decimal` | Sum of all position market values plus cash |
| `allocations()` | `dict[str, Allocation]` | Per-asset actual percentage of total value |

## Commands

```bash
just test -k test_models    # model unit tests
```

## See Also

- [Analysis](../analysis/) — computes deviations from `PortfolioSnapshot`
- [Rules](../rules/) — `evaluate()` receives `PortfolioSnapshot` and produces `Signal`
- [Templates](../templates/) — renders `Signal` and `DeviationResult` into messages
- [TR Client](../tr/) — builds `PortfolioSnapshot` from Trade Republic WebSocket data
