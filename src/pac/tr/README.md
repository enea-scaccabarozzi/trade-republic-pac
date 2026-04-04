# Trade Republic Client

Read-only WebSocket client for fetching portfolio data from Trade Republic via the `pytr` library. All connections are per-request through the `tr_session()` context manager.

## Architectural Role

| Aspect      | Details                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------ |
| Depends on  | [`models`](../models/) (`PortfolioSnapshot`, `Position`, `SavingsPlan`), [`config`](../config/) (`Settings`) |
| Consumed by | [`app.py`](../app.py) (portfolio fetching), [`delivery`](../delivery/) (interactive command handling)        |
| Boundary    | Edge adapter — translates pytr WebSocket API into typed domain models                                        |

## Key Components

| Component               | File            | Description                                                              |
| ----------------------- | --------------- | ------------------------------------------------------------------------ |
| `TRClient`              | `client.py`     | Async client wrapping pytr's `TradeRepublicApi` for read-only operations |
| `tr_session()`          | `client.py`     | Async context manager — connects, yields client, closes on exit          |
| `TRClientError`         | `exceptions.py` | Base exception for all TR client errors                                  |
| `TRConnectionError`     | `exceptions.py` | WebSocket connection failure or timeout                                  |
| `TRSessionExpiredError` | `exceptions.py` | Session cookies expired — re-authentication required                     |

## Configuration

Connection credentials are read from `Settings.broker`:

| Field          | Source                | Description                                                  |
| -------------- | --------------------- | ------------------------------------------------------------ |
| `phone_number` | `broker.phone_number` | Trade Republic account phone                                 |
| `pin`          | `broker.pin`          | Account PIN                                                  |
| `cookies_path` | `broker.cookies_path` | Path for session cookie storage (default: `/tmp/tr_cookies`) |

All secrets should use `${ENV_VAR}` interpolation in `pac.yaml`.

## Usage

```python
from pac.config import load_config
from pac.tr import tr_session, TRConnectionError

settings = load_config()

async with tr_session(settings) as client:
    snapshot = await client.get_portfolio()    # PortfolioSnapshot
    cash = await client.get_cash_balance()     # Decimal
    plans = await client.get_savings_plans()   # list[SavingsPlan]
```

### `TRClient` Methods

| Method                | Returns             | Description                                   |
| --------------------- | ------------------- | --------------------------------------------- |
| `connect()`           | `None`              | Opens WebSocket, resumes session from cookies |
| `close()`             | `None`              | Closes the WebSocket connection               |
| `get_portfolio()`     | `PortfolioSnapshot` | Fetches positions, cash, and ticker prices    |
| `get_cash_balance()`  | `Decimal`           | Fetches available cash balance                |
| `get_savings_plans()` | `list[SavingsPlan]` | Fetches configured savings plans              |

### Error Handling

All exceptions inherit from `TRClientError`:

```
TRClientError
├── TRConnectionError        # connection failure, timeout
└── TRSessionExpiredError    # cookies expired, needs re-auth
```

## Commands

```bash
just test -k test_client    # TR client unit tests
```

## See Also

- [Models](../models/) — `PortfolioSnapshot`, `Position`, `SavingsPlan` produced by the client
- [Config](../config/) — `BrokerConfig` provides connection credentials
- [Orchestrator](../orchestrator/) — calls `tr_session()` during signal dispatch
