# Testing Rules

## Core Principles

1. **Black-box testing** — test observable behavior, never internals. Verify what a function returns or what side effects it produces, not how it achieves them.
2. **DI-first** — all external dependencies are injected and faked at the boundary. The module under test uses real code; only its collaborators are faked.
3. **No mocking internals** — never patch private methods or internal state of the unit under test.

## Decision Matrix

| Change Type                   | Approach                                          |
| ----------------------------- | ------------------------------------------------- |
| New signal rule               | BDD feature + unit edge cases                     |
| New delivery channel          | BDD feature + lifecycle tests                     |
| Config validation             | BDD feature (comprehensive)                       |
| Analysis pure function        | Unit tests (edge cases, boundaries)               |
| Template rendering            | BDD feature                                       |
| Auto-discovery                | BDD feature                                       |
| HTTP endpoints                | Integration tests in `tests/test_app.py`          |
| Orchestrator pipeline         | BDD feature + unit tests                          |
| BacktestStrategy              | Unit tests + BDD for observable strategy behavior |
| Research framework capability | BDD feature                                       |
| Pure indicator math           | Unit tests (numeric precision)                    |

Add unit tests beyond BDD when: edge cases, boundary values, error handling, parameterised math with many numeric combinations.

## `make_settings()` Factory

All settings fixtures use `make_settings()` from `tests/conftest.py`. It builds a valid `Settings` with test defaults and accepts keyword overrides:

```python
from tests.conftest import make_settings

settings = make_settings()  # all defaults
settings = make_settings(signals=[])  # override one field
```

Never construct `Settings` directly in tests — use `make_settings()`.

## Mocking Boundaries

| Boundary                 | Mock? | How                                                         |
| ------------------------ | ----- | ----------------------------------------------------------- |
| TR WebSocket API         | Yes   | Patch `tr_session` in orchestrator tests                    |
| Telegram Bot API         | Yes   | Patch PTB `Application.bot.send_message`                    |
| Filesystem (config YAML) | Yes   | Write temp YAML via `tmp_path` fixture                      |
| Environment variables    | Yes   | `monkeypatch.setenv()` / `monkeypatch.delenv()`             |
| yfinance (backtester)    | Yes   | Inject pre-built `dict[str, PriceSeries]` fixtures directly |
| Module under test        | No    | Use real implementation                                     |
| Pydantic validation      | No    | Use real model — faking validators hides bugs               |
| Internal helpers         | No    | Part of the module under test                               |
| Other submodules (rules) | No    | Pass real `DeviationReport` fixtures                        |

## DI Patterns

### Root `tests/conftest.py` — `make_settings()` Factory

```python
def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "version": 1,
        "broker": {"type": "trade_republic", "phone_number": "+491234567890", "pin": "1234"},
        "assets": [
            {"id": "stocks", "name": "Stocks ETF", "isin": "IE00BK5BQT80", "target_pct": 70},
            {"id": "gold", "name": "Gold ETC", "isin": "IE00B4ND3602", "target_pct": 15},
            {"id": "bonds", "name": "Bond ETF", "isin": "IE00B3F81409", "target_pct": 15},
        ],
        "app": {"job_secret": "test-job-secret"},
        "channels": {"telegram": {"type": "telegram", "bot_token": "fake-token", "chat_id": "12345",
                                   "webhook": {"url": "", "secret": "test-webhook-secret"}}},
        "signals": [],
    }
    base.update(overrides)
    return Settings.model_validate(base)
```

### Faking the TR WebSocket Client

```python
@pytest.fixture()
def mock_tr_session(sample_snapshot: PortfolioSnapshot) -> Any:
    mock_client = AsyncMock()
    mock_client.get_portfolio = AsyncMock(return_value=sample_snapshot)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("pac.orchestrator.orchestrator.tr_session", return_value=mock_ctx) as p:
        yield p
```

### Faking MarketDataProvider (Backtester Tests)

Inject pre-built `PriceSeries` objects directly — no yfinance calls:

```python
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

## Backtester Testing Patterns

### Testing BacktestStrategy

`BacktestStrategy.reset()` clears per-iteration state. Tests must verify reset actually works:

```python
def test_cooldown_clears_after_reset(strategy, signals, snapshot, report):
    strategy.on_signals(signals, snapshot, report, date(2023, 1, 10))
    strategy.reset()
    result = strategy.on_signals(signals, snapshot, report, date(2023, 1, 11))
    assert len(result) > 0  # should fire again after reset
```

### Monte Carlo: Fast Deterministic Fixture

Use `monte_carlo_iterations=1` for tests that need a full simulation but should be fast:

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

## Commands

```bash
just test                               # all tests
just test -k test_deviation             # single test by name
just test -k "test_config and not bdd"  # unit tests only for config
just test -k test_threshold_rule_bdd    # single BDD feature
just test -k backtester                 # all backtester tests
just validate                           # lint + typecheck + test
```
