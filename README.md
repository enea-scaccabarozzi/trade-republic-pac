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

## Setup Scripts

Interactive CLI scripts that guide you through onboarding and deployment. Each script caches results in `.pac/` (gitignored) and supports `--override` to re-run cached steps.

#### Guided Setup (recommended for first-time users)

Clone the repo and run the interactive setup:

```bash
git clone https://github.com/enea-scaccabarozzi/trade-republic-pac.git
cd trade-republic-pac
just sync     # install dependencies
just setup    # interactive guided setup (TR → Telegram → GCP → .env)
just run      # start the application
```

`just setup` runs all three setup scripts in dependency order:
1. **Trade Republic** — validates API credentials and stores session
2. **Telegram** — creates bot via BotFather, polls for `/start` (webhook registration is deferred)
3. **GCP** — deploys Cloud Run, registers Telegram webhook, creates scheduler jobs
4. **generate-env** — writes `.env` from cached results

#### Manual Setup

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# Edit .env with your credentials
```

See `.env.example` for all required variables and their descriptions.

#### Running Individual Steps

Run all steps in sequence:

```bash
just setup
```

Or run individual steps:

```bash
just setup-tr                          # Trade Republic credentials
just setup-telegram                    # Telegram bot creation
just setup-gcp                         # GCP Cloud Run deployment
just setup-webhook                     # Register webhook (after Telegram + GCP)
just generate-env                      # Regenerate .env from caches
```

#### Three Setup Paths

| Path                  | Steps                                                                                               | When to use                                |
| --------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Full `just setup`** | `just setup` (runs all 3 scripts + generate-env)                                                    | First-time users, easiest path             |
| **Partial scripts**   | Run `just setup-tr`, `just setup-telegram`, `just setup-gcp` individually, then `just generate-env` | Re-running one step, or customizing order  |
| **Full manual**       | Copy `.env.example` to `.env`, fill in all values by hand                                           | CI/CD, Docker-only, no interactive prompts |

> **Note:** If you run `just setup-telegram` standalone (without `--skip-webhook`), the script will prompt for a webhook URL if GCP hasn't been set up yet. To avoid the prompt, pass `--skip-webhook` and register the webhook later with `just setup-webhook`.

### Trade Republic Setup (`just setup-tr`)

Sets up and validates Trade Republic API credentials.

**What it does:**
- Connects to the Trade Republic API (read-only) via `pytr`
- Runs the 2FA verification flow (app notification or SMS fallback)
- Saves session cookies locally for future API access

**Prerequisites:**
- A Trade Republic account with an active portfolio
- The Trade Republic app installed (for 2FA code delivery)

**Usage:**

```bash
# Interactive (recommended)
just setup-tr

# Non-interactive (CI)
TR_PIN=1234 just setup-tr --phone +491234567890

# Re-run even if cached
just setup-tr --override
```

**CLI flags:**
| Flag         | Description                                            |
| ------------ | ------------------------------------------------------ |
| `--phone`    | TR phone number in E.164 format (e.g. `+491234567890`) |
| `--override` | Re-run setup even if `.pac/tr.json` exists             |

**What it creates:**
- `.pac/tr.json` — cached setup state (phone, masked PIN, cookies path)
- `.pac/tr_cookies` — pytr session cookies

**Security notes:**
- Your PIN is **never stored** in the cache — only a masked placeholder
- PIN input is either prompted with masked input or read from the `TR_PIN` environment variable
- PIN is **never accepted as a CLI flag** (to avoid shell history leaks)
- Session cookies are stored in `.pac/tr_cookies` — treat this file as sensitive

### GCP Deployment (`just setup-gcp`)

Deploys the application to Google Cloud Run with Cloud Scheduler jobs.

**What it does:**
- Creates or selects a GCP project
- Enables required APIs (Cloud Run, Cloud Scheduler, Artifact Registry)
- Builds and pushes the Docker image to Artifact Registry
- Deploys a Cloud Run service with environment variables
- Sets webhook-related environment variables (`TELEGRAM_WEBHOOK_URL`, `TELEGRAM_WEBHOOK_SECRET`) on the Cloud Run service
- Registers the Telegram webhook with the Bot API (`setWebhook`) using cached bot token
- Creates Cloud Scheduler jobs for each signal defined in `pac.yaml`

**Prerequisites:**
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud auth login`)
- [Docker](https://docs.docker.com/get-docker/) installed and running
- `pac.yaml` configured (copy from `pac.yaml.example`)
- GCP billing enabled on the target project

**Usage:**

```bash
# Interactive (recommended)
just setup-gcp

# Non-interactive
just setup-gcp --project my-project --region europe-west1 --service-name trade-republic-pac

# Re-run even if cached
just setup-gcp --override
```

**CLI flags:**
| Flag             | Description                                            |
| ---------------- | ------------------------------------------------------ |
| `--project`      | GCP project ID (lists existing projects if omitted)    |
| `--region`       | GCP region (default: `europe-west1`)                   |
| `--service-name` | Cloud Run service name (default: `trade-republic-pac`) |
| `--override`     | Re-run setup even if `.pac/gcp.json` exists            |

**What it creates:**
- `.pac/gcp.json` — cached deployment state (project, region, service URL, image URI, scheduler jobs)
- GCP resources: Artifact Registry repo, Cloud Run service, Cloud Scheduler jobs

**Cost estimates (within free tier for typical usage):**
- Cloud Run: ~2M requests/month free
- Cloud Scheduler: 3 free jobs, then $0.10/job/month
- Artifact Registry: 0.5 GB free storage

**Security notes:**
- The Cloud Run service is **publicly accessible** (required for Telegram webhook delivery) — authentication is enforced at the application level via HMAC headers (`X-Job-Secret`, `X-Telegram-Bot-Api-Secret-Token`)
- Environment variables (including secrets) are passed via a temporary file that is deleted immediately after deployment
- Cloud Scheduler job secrets (`X-Job-Secret` header) may appear in GCP audit logs — these logs are only accessible to project admins

### Telegram Bot Setup (`just setup-telegram`)

Creates a Telegram bot via BotFather, retrieves your chat ID, and registers a webhook.

**What it does:**
- Logs into your personal Telegram account via Telethon (MTProto)
- Sends commands to @BotFather to create a new bot
- Polls for your `/start` message to obtain your `chat_id`
- Registers a webhook URL with the Telegram Bot API
- Cleans up the Telethon session file after completion

**Prerequisites:**
- A personal Telegram account
- API credentials (`api_id` and `api_hash`) from [my.telegram.org](https://my.telegram.org)
- A webhook URL (auto-detected from `.pac/gcp.json` if GCP setup was run first)

**Usage:**

```bash
# Interactive (recommended)
just setup-telegram

# Non-interactive (API credentials + bot config only — phone is still prompted)
TELEGRAM_API_ID=12345 TELEGRAM_API_HASH=abc123 \
  just setup-telegram --bot-name "My PAC Bot" --bot-username my_pac_bot

# Skip webhook (register later with setup-webhook or setup-gcp)
just setup-telegram --skip-webhook

# Re-run even if cached
just setup-telegram --override

# Register webhook separately (after GCP deploy)
just setup-webhook

# Re-register webhook
just setup-webhook --override
```

> **Note:** Your Telegram phone number is always prompted interactively for security — it cannot be passed as a CLI flag or environment variable. In the `just setup` flow, webhook registration is deferred to the GCP step.

**CLI flags:**
| Flag             | Description                                                             |
| ---------------- | ----------------------------------------------------------------------- |
| `--bot-name`     | Bot display name (e.g. "My PAC Bot")                                    |
| `--bot-username` | Bot username — must end in `bot` (e.g. `my_pac_bot`)                    |
| `--override`     | Re-run setup even if `.pac/telegram.json` exists                        |
| `--skip-webhook` | Skip webhook registration (done later by GCP deploy or `setup-webhook`) |

**Environment variable fallbacks:**
| Variable            | Description                                           |
| ------------------- | ----------------------------------------------------- |
| `TELEGRAM_API_ID`   | Telegram API ID (number) — skips interactive prompt   |
| `TELEGRAM_API_HASH` | Telegram API hash (string) — skips interactive prompt |

> Phone number is **not** configurable via env var or CLI flag — it is always prompted interactively to avoid leaking it in shell history or process lists.

**What it creates:**
- `.pac/telegram.json` — cached setup state (bot token, username, chat ID, webhook URL/secret)

**Security notes:**
- The Telethon session file (`.pac/telethon.session`) is **automatically deleted** after bot creation to avoid leaving personal Telegram auth material on disk
- Bot token and webhook secret are sensitive credentials — they are **never accepted as CLI flags** (to avoid shell history leaks)
- If bot creation succeeds but chat_id polling is interrupted, the script saves a partial cache and resumes from chat_id polling on the next run

## Configuration

All configuration lives in a single YAML file (`pac.yaml`). See [`pac.yaml.example`](pac.yaml.example) for a ready-to-use template.

Secrets are kept out of the YAML file using `${ENV_VAR}` interpolation — the config loader substitutes environment variable values at load time.

### How `.env` and `pac.yaml` Work Together

- **`pac.yaml`** defines application structure: assets, signals, channels, server settings.
- **`.env`** holds secrets (API keys, PINs, tokens) that `pac.yaml` references via `${ENV_VAR}` interpolation.
- At startup, `.env` is loaded automatically (via `python-dotenv`). Environment variables from Docker/Cloud Run take precedence.
- Setup scripts (`just setup`) populate `.env` from interactive input. You can also edit `.env` manually.
- To regenerate `.env` from cached setup results: `just generate-env`

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

## Backtesting

Validate your signal and strategy configuration against historical price data before deploying live.

### Quick Start

Install the backtest dependencies:

```bash
uv sync --group backtest
```

Launch the interactive CLI:

```bash
uv run python -m pac.backtester
# or
just backtest
```

### Commands

| Command      | Description                                            |
| ------------ | ------------------------------------------------------ |
| `run`        | Run a backtest with a selected strategy and date range |
| `strategies` | List all available strategies                          |
| `results`    | List saved backtest results                            |
| `show`       | Display metrics and equity curve for a saved result    |

Tickers for historical data are configured alongside each asset in `pac.yaml`. See [`pac.yaml.example`](pac.yaml.example) for reference.

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
