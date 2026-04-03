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

## Quick Start

Pull the Docker image:

```bash
docker pull ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest
```

Download and fill in the environment file:

```bash
curl -O https://raw.githubusercontent.com/enea-scaccabarozzi/trade-republic-pac/main/.env.example
cp .env.example .env
# Edit .env with your credentials
```

### Test Run

```bash
docker run --rm --env-file .env ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest
```

### Persistent Deployment

Create a `compose.yml`:

```yaml
services:
  pac:
    image: ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest
    env_file: .env
    restart: unless-stopped
```

```bash
docker compose up -d
```

## Configuration

All configuration via environment variables with `PAC_` prefix. See `.env.example` for a ready-to-use template.

### Trade Republic Credentials

| Variable              | Required | Default           | Description                |
| --------------------- | -------- | ----------------- | -------------------------- |
| `PAC_TR_PHONE_NUMBER` | Yes      | —                 | TR account phone number    |
| `PAC_TR_PIN`          | Yes      | —                 | TR account PIN             |
| `PAC_TR_COOKIES_PATH` | No       | `/tmp/tr_cookies` | Path to TR session cookies |

### Telegram

| Variable                 | Required | Default | Description            |
| ------------------------ | -------- | ------- | ---------------------- |
| `PAC_TELEGRAM_BOT_TOKEN` | Yes      | —       | Telegram bot API token |
| `PAC_TELEGRAM_CHAT_ID`   | Yes      | —       | Telegram chat ID       |

### Webhook & Scheduling

| Variable             | Required | Default | Description                         |
| -------------------- | -------- | ------- | ----------------------------------- |
| `PAC_WEBHOOK_URL`    | No       | `""`    | Public URL for Telegram webhook     |
| `PAC_WEBHOOK_SECRET` | Yes      | —       | Secret for Telegram webhook header  |
| `PAC_JOB_SECRET`     | Yes      | —       | Secret token for scheduled job auth |

### Target Allocation

| Variable                | Required | Default | Description               |
| ----------------------- | -------- | ------- | ------------------------- |
| `PAC_TARGET_STOCKS_PCT` | No       | `70`    | Stock allocation target % |
| `PAC_TARGET_GOLD_PCT`   | No       | `15`    | Gold allocation target %  |
| `PAC_TARGET_BONDS_PCT`  | No       | `15`    | Bond allocation target %  |

### Asset ISINs

| Variable          | Required | Default        | Description             |
| ----------------- | -------- | -------------- | ----------------------- |
| `PAC_ISIN_STOCKS` | No       | `IE00BK5BQT80` | FTSE All-World ETF ISIN |
| `PAC_ISIN_GOLD`   | No       | `IE00B4ND3602` | Physical Gold ETC ISIN  |
| `PAC_ISIN_BONDS`  | No       | `IE00B3F81409` | Gov Bond ETF ISIN       |

### Deviation Thresholds

| Variable                      | Required | Default | Description                                  |
| ----------------------------- | -------- | ------- | -------------------------------------------- |
| `PAC_DEVIATION_WARNING_PCT`   | No       | `3.0`   | Deviation % for warning signal               |
| `PAC_DEVIATION_CRITICAL_PCT`  | No       | `5.0`   | Deviation % for critical signal              |
| `PAC_CYCLE_INVERSION_MIN_PCT` | No       | `2.0`   | Min deviation % per side for cycle inversion |

### PAC Settings

| Variable                 | Required | Default  | Description                         |
| ------------------------ | -------- | -------- | ----------------------------------- |
| `PAC_PAC_MONTHLY_BUDGET` | No       | `500.00` | Monthly PAC investment budget (EUR) |
| `PAC_PAC_DAY_OF_MONTH`   | No       | `14`     | Day of month for PAC calculation    |

> For development-only variables (`PAC_DEV`, etc.), see [CONTRIBUTING.md](CONTRIBUTING.md).

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

## For Developers

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, commit conventions, and PR guidelines.
A [dev container](.devcontainer/devcontainer.json) configuration is included for VS Code and GitHub Codespaces — it handles all tooling setup automatically.

## AI Disclaimer

> This repository was heavily developed with the assistance of AI coding agents. For details on the AI-assisted development workflow, see [enea-scaccabarozzi/coding-agents](https://github.com/enea-scaccabarozzi/coding-agents).

## License

Licensed under the [GNU General Public License v3.0](LICENSE).
