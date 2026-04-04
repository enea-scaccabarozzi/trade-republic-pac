# Trade Republic PAC

Automated portfolio rebalancing assistant for Trade Republic.

[![CI](https://github.com/enea-scaccabarozzi/trade-republic-pac/actions/workflows/ci.yml/badge.svg)](https://github.com/enea-scaccabarozzi/trade-republic-pac/actions/workflows/ci.yml)
[![Release](https://github.com/enea-scaccabarozzi/trade-republic-pac/actions/workflows/release.yml/badge.svg)](https://github.com/enea-scaccabarozzi/trade-republic-pac/actions/workflows/release.yml)
[![License: GPL-3.0](https://img.shields.io/github/license/enea-scaccabarozzi/trade-republic-pac)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)
[![Docker: ghcr.io](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/enea-scaccabarozzi/trade-republic-pac/pkgs/container/trade-republic-pac)

## What It Does

Reads your Trade Republic portfolio via the `pytr` library (read-only), detects deviations from a configurable target allocation (default 70/15/15: FTSE All-World / Gold / Gov Bonds), and sends Telegram notifications with rebalancing recommendations. **This tool never executes trades** — all recommendations are advisory only.

## Features

- **Hourly signal checks** — Monitors portfolio alignment, alerts on threshold breaches and cycle inversions
- **Monthly PAC redistribution** — On a configurable day of the month, calculates optimal savings plan volumes from available balance
- **Telegram bot** — `/status`, `/rebalance`, `/redistribute`, `/help` commands with inline keyboards
- **Configurable target allocation** — Default 70/15/15, fully adjustable via environment variables
- **Self-hosted Docker container** — Single image, deploy anywhere

## Repository Structure

```
src/pac/
├── __main__.py               # Structlog config + uvicorn runner
├── app.py                    # Starlette ASGI app (webhook, job, health endpoints)
├── config/                   # Settings loaded from pac.yaml (YAML + pydantic validation)
├── models/                   # Pydantic data models (portfolio, signals)
├── tr/                       # TRClient wrapper + tr_session() context manager
├── analysis/                 # Deviation calculation, PAC redistribution
├── rules/                    # SignalRule protocol, registry, builtin rules
│   └── builtin/              # Threshold, cycle inversion rules
├── delivery/                 # Delivery channel abstraction
│   └── channels/telegram/    # Telegram bot, formatting, keyboards
├── templates/                # Template engine + format adapters
└── orchestrator/             # Signal dispatch orchestration
tests/                        # Shared fixtures + integration tests
docs/                         # Project documentation + ADRs
```

Each submodule has co-located `tests/`, `features/`, and `README.md`.

## Quick Start

Pull the Docker image:

```bash
docker pull ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest
```

Download and customise the config file:

```bash
curl -O https://raw.githubusercontent.com/enea-scaccabarozzi/trade-republic-pac/main/pac.yaml.example
cp pac.yaml.example pac.yaml
# Edit pac.yaml — secrets use ${ENV_VAR} interpolation
```

Set required environment variables for secrets referenced in `pac.yaml`:

```bash
export PAC_JOB_SECRET="your-job-secret"
export TR_PHONE_NUMBER="+49..."
export TR_PIN="1234"
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="987654321"
export TELEGRAM_WEBHOOK_URL="https://your-domain.com/webhook"
export TELEGRAM_WEBHOOK_SECRET="your-webhook-secret"
```

### Test Run

```bash
docker run --rm \
  -v "$(pwd)/pac.yaml:/app/pac.yaml:ro" \
  -e PAC_JOB_SECRET -e TR_PHONE_NUMBER -e TR_PIN \
  -e TELEGRAM_BOT_TOKEN -e TELEGRAM_CHAT_ID \
  -e TELEGRAM_WEBHOOK_URL -e TELEGRAM_WEBHOOK_SECRET \
  ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest
```

### Persistent Deployment

Create a `compose.yml`:

```yaml
services:
  pac:
    image: ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest
    volumes:
      - ./pac.yaml:/app/pac.yaml:ro
    environment:
      - PAC_JOB_SECRET
      - TR_PHONE_NUMBER
      - TR_PIN
      - TELEGRAM_BOT_TOKEN
      - TELEGRAM_CHAT_ID
      - TELEGRAM_WEBHOOK_URL
      - TELEGRAM_WEBHOOK_SECRET
    restart: unless-stopped
```

```bash
docker compose up -d
```

## Configuration

All configuration lives in a single YAML file (`pac.yaml`). See [`pac.yaml.example`](pac.yaml.example) for a ready-to-use template.

Secrets are kept out of the YAML file using `${ENV_VAR}` interpolation — the config loader substitutes environment variable values at load time.

### Config File Location

The loader searches for config in this order:

1. Explicit path passed to `load_config()`
2. `PAC_CONFIG_PATH` environment variable
3. `pac.yaml` in the current working directory

### Config Structure

```yaml
version: 1

app:
  log_level: INFO          # Log level (DEBUG, INFO, WARNING, ERROR)
  dev_mode: false           # Enable dev mode
  port: 8080                # Server port
  job_secret: "${PAC_JOB_SECRET}"  # HMAC secret for job endpoints

broker:
  type: trade_republic
  phone_number: "${TR_PHONE_NUMBER}"
  pin: "${TR_PIN}"
  cookies_path: /tmp/tr_cookies

assets:                     # Dynamic — add/remove/rename freely
  - id: stocks
    name: Stocks ETF
    isin: IE00BK5BQT80
    target_pct: 70
  - id: gold
    name: Gold ETC
    isin: IE00B4ND3602
    target_pct: 15
  - id: bonds
    name: Bond ETF
    isin: IE00B3F81409
    target_pct: 15

channels:                   # Delivery channel configs (validated per-channel)
  telegram:
    type: telegram
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
    webhook:
      url: "${TELEGRAM_WEBHOOK_URL}"
      secret: "${TELEGRAM_WEBHOOK_SECRET}"

signals: []                 # Signal rule definitions (validated per-rule)
```

Assets are fully dynamic — there is no fixed enum. Each asset has a string `id`, display `name`, `isin`, and `target_pct`. Target percentages are validated but do not need to sum to 100 at the model level.

> For development setup and commands, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Architecture

```
Telegram API ──POST /webhook──▶ ┌────────────────────┐
                                │  Starlette ASGI    │
Scheduler    ──POST /jobs/*────▶│  (Docker)          │──▶ TR WebSocket API
                                │                    │
                                │  GET /health       │
                                └────────────────────┘
```

Starlette ASGI application running in a Docker container. Telegram webhook handles bot commands, scheduler endpoints trigger hourly signal checks and monthly PAC calculations, and a health endpoint is available for container orchestrators.

### Endpoints

| Path                 | Method | Auth                              | Description               |
| -------------------- | ------ | --------------------------------- | ------------------------- |
| `/webhook`           | POST   | `X-Telegram-Bot-Api-Secret-Token` | Telegram bot updates      |
| `/jobs/hourly-check` | POST   | `X-Job-Secret`                    | Run signal evaluation     |
| `/jobs/monthly-pac`  | POST   | `X-Job-Secret`                    | Calculate & send PAC plan |
| `/health`            | GET    | —                                 | Health check              |

## Telegram Commands

| Command         | Description                                |
| --------------- | ------------------------------------------ |
| `/start`        | Greet and list available commands          |
| `/help`         | Show available commands (alias for /start) |
| `/status`       | Portfolio allocation & deviations          |
| `/rebalance`    | Evaluate rebalance signals                 |
| `/redistribute` | Calculate monthly PAC plan                 |

## Extending

Add custom signal rules and delivery channels with scaffolding commands:

```bash
just new-rule my_rule       # scaffold a signal rule
just new-channel my_channel # scaffold a delivery channel
just validate-config        # validate pac.yaml references
```

See [CONTRIBUTING.md](CONTRIBUTING.md#extending-the-system) for detailed guides.

## For Developers

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, commit conventions, and PR guidelines.
A [dev container](.devcontainer/devcontainer.json) configuration is included for VS Code and GitHub Codespaces — it handles all tooling setup automatically.

## AI Disclaimer

> This repository was heavily developed with the assistance of AI coding agents. For details on the AI-assisted development workflow, see [enea-scaccabarozzi/coding-agents](https://github.com/enea-scaccabarozzi/coding-agents).

## License

Licensed under the [GNU General Public License v3.0](LICENSE).
