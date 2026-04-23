# Testing Philosophy

This guide covers the project's approach to testing: black-box testing, dependency injection patterns, mocking boundaries, and when to use BDD vs unit tests.

## Core Principles

1. **Black-box testing** — test observable behavior, never internals. Verify what a function returns or what side effects it produces, not how it achieves them.
1. **DI-first** — all external dependencies are injected and faked at the boundary. The module under test uses real code; only its collaborators are faked.
1. **No mocking internals under test** — never patch private methods or internal state of the thing you're testing.

## Decision Matrix: What to Test and How

| Change Type | Approach | Example |
| ---------------------- | ----------------------------------- | -------------------------------------------------------- |
| New signal rule | BDD feature + unit edge cases | `threshold_rule.feature` + `test_signals.py` |
| New delivery channel | BDD feature + lifecycle tests | `telegram_delivery.feature` + `test_telegram_channel.py` |
| Config validation | BDD feature (comprehensive) | `config_loading.feature` (15 scenarios) |
| Analysis pure function | Unit tests (edge cases, boundaries) | `test_deviation.py`, `test_rebalance.py` |
| Template rendering | BDD feature | `template_rendering.feature`, `format_adapters.feature` |
| Auto-discovery | BDD feature | `rule_discovery.feature`, `channel_discovery.feature` |
| HTTP endpoints | Integration tests | `tests/test_app.py` |
| Orchestrator pipeline | BDD feature + unit tests | `signal_dispatch.feature` + `test_orchestrator.py` |

### When to Add Tests Beyond BDD

BDD scenarios cover the happy path and key error paths. Add unit tests when:

1. **Edge cases** — empty portfolio, zero budget, single asset, all assets overweight
1. **Boundary values** — deviation exactly at threshold, budget rounding to cents
1. **Error handling** — specific exception types, error messages
1. **Parameterized math** — analysis functions with many numeric input combinations

Real example: `test_deviation.py` has unit tests for cash-in-denominator edge cases that would be awkward as Gherkin scenarios because they test numeric precision.

## DI Patterns in This Repo

### Root `tests/conftest.py` — `make_settings()` Factory

All settings fixtures use the `make_settings()` factory. It builds a fully valid `Settings` with test defaults and allows overrides:

```python
# tests/conftest.py
def make_settings(**overrides: Any) -> Settings:
    """Build a Settings instance with test defaults."""
    base: dict[str, Any] = {
        "version": 1,
        "broker": {
            "type": "trade_republic",
            "phone_number": "+491234567890",
            "pin": "1234",
        },
        "assets": [
            {"id": "stocks", "name": "Stocks ETF", "isin": "IE00BK5BQT80", "target_pct": 70},
            {"id": "gold", "name": "Gold ETC", "isin": "IE00B4ND3602", "target_pct": 15},
            {"id": "bonds", "name": "Bond ETF", "isin": "IE00B3F81409", "target_pct": 15},
        ],
        "app": {"job_secret": "test-job-secret"},
        "channels": {"telegram": {"type": "telegram", "bot_token": "fake-token", "chat_id": "12345", "webhook": {"url": "", "secret": "test-webhook-secret"}}},
        "signals": [],
    }
    base.update(overrides)
    return Settings.model_validate(base)
```

### Per-Module Shared Fixtures

Each submodule's `conftest.py` provides domain-specific fixtures built from real Pydantic models:

```python
# src/pac/rules/tests/conftest.py
@pytest.fixture
def sample_positions() -> list[Position]:
    return [
        Position(isin="IE00BK5BQT80", name="Vanguard FTSE All-World",
                 quantity=Decimal("10"), price=Decimal("100.00"),
                 market_value=Decimal("1000.00"), asset_id="stocks"),
        # ...gold, bonds...
    ]

@pytest.fixture
def sample_snapshot(sample_positions: list[Position]) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        positions=sample_positions,
        cash=Decimal("200.00"),
        timestamp=datetime(2026, 4, 1, tzinfo=UTC),
    )

@pytest.fixture
def default_settings() -> Settings:
    return make_settings()
```

### Faking the TR WebSocket Client

The orchestrator tests fake the TR session at the boundary — no network calls:

```python
# src/pac/orchestrator/tests/test_orchestrator.py
@pytest.fixture()
def mock_tr_session(sample_snapshot: PortfolioSnapshot) -> Any:
    """Patch tr_session to return a mock client with get_portfolio()."""
    mock_client = AsyncMock()
    mock_client.get_portfolio = AsyncMock(return_value=sample_snapshot)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("pac.orchestrator.orchestrator.tr_session", return_value=mock_ctx) as p:
        yield p
```

### Faking MarketDataProvider (Backtester Tests)

The backtester tests inject pre-built `PriceSeries` objects directly — no yfinance calls:

```python
from pac.backtester.data.models import PriceBar, PriceSeries
from decimal import Decimal
from datetime import date

@pytest.fixture
def price_data() -> dict[str, PriceSeries]:
    bars = [
        PriceBar(
            date=date(2023, 1, d), open=Decimal("100"), high=Decimal("105"),
            low=Decimal("98"), close=Decimal("102"), volume=1000,
        )
        for d in range(2, 32)
    ]
    return {"stocks": PriceSeries(ticker="EUNL.DE", bars=bars)}
```

### Testing BacktestStrategy

`BacktestStrategy.reset()` clears per-iteration state (e.g., cooldown dates). Tests must verify that `reset()` actually resets the strategy:

```python
def test_cooldown_clears_after_reset(strategy, signals, snapshot, report):
    # first call sets cooldown
    strategy.on_signals(signals, snapshot, report, date(2023, 1, 10))
    strategy.reset()
    # should fire again after reset, not be suppressed by cooldown
    result = strategy.on_signals(signals, snapshot, report, date(2023, 1, 11))
    assert len(result) > 0
```

### Monte Carlo: Fast Deterministic Fixture

Use `monte_carlo_iterations=1` for tests that need a full simulation run but should be fast:

```python
@pytest.fixture
def backtest_config() -> BacktestConfig:
    return BacktestConfig(
        strategy="pac_alignment",
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
        initial_cash=Decimal("10000"),
        monthly_contribution=Decimal("500"),
        monte_carlo_iterations=1,
    )
```

## Mocking Boundaries

| Boundary | Mock? | How | Example File |
| ------------------------ | ----- | ------------------------------------------------------ | ----------------------------------------- |
| TR WebSocket API | ✅ Yes | Patch `tr_session` in orchestrator | `orchestrator/tests/test_orchestrator.py` |
| Telegram Bot API | ✅ Yes | Patch PTB `Application.bot.send_message` | `delivery/tests/test_telegram_channel.py` |
| Filesystem (config YAML) | ✅ Yes | Write temp YAML files via `tmp_path` fixture | `config/tests/test_config_loading_bdd.py` |
| Environment variables | ✅ Yes | `monkeypatch.setenv()` / `monkeypatch.delenv()` | `config/tests/test_config_loading_bdd.py` |
| Module under test | ❌ No | Use real implementation | — |
| Pydantic validation | ❌ No | Use real model — faking validators hides bugs | — |
| Internal helpers | ❌ No | Part of the module under test | — |
| Other submodules (rules) | ❌ No | Pass real DeviationReport fixtures, not mocked reports | `rules/tests/conftest.py` |

**Anti-pattern:** "Don't mock the `SignalRegistry` to test `ThresholdDeviationRule`." Create a real `DeviationReport` fixture and pass it to `rule.evaluate()`.

**Good pattern:** "Create real Pydantic model instances as fixtures, inject them into the function under test."

## Test Organization

| Location | Contains |
| ------------------------------------------- | ---------------------------------------------- |
| `src/pac/<module>/tests/` | Co-located module tests |
| `src/pac/<module>/tests/conftest.py` | Module-specific fixtures |
| `src/pac/<module>/tests/test_<name>_bdd.py` | BDD step definitions |
| `src/pac/<module>/tests/test_<name>.py` | Unit / edge-case tests |
| `tests/conftest.py` | Shared fixtures (`make_settings()`, snapshots) |
| `tests/test_app.py` | Integration tests for HTTP endpoints |
| `tests/test_scaffold_rule.py` | DX script tests |

## Commands

```bash
just test                               # all tests
just test -k test_deviation             # single test by name
just test -k "test_config and not bdd"  # unit tests only for config
just test -k test_threshold_rule_bdd    # single BDD feature
just test -k backtester                 # backtester tests only
just validate                           # lint + typecheck + test
```

## Coverage Philosophy

- Aim for high **behavioral** coverage, not line coverage
- Pure functions (`analysis/`) deserve exhaustive edge-case testing
- Framework glue (discovery, wiring) is covered by BDD scenarios
- Skip testing: trivial property accessors, `__repr__`, default `__init__` constructors
- Focus on: decision branches, error paths, boundary values
