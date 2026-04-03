# Trade Republic PAC Automation

Automated portfolio rebalancing assistant for Trade Republic. Reads portfolio data
via the `pytr` library (read-only), calculates deviations from a target allocation
(70/15/15: FTSE All-World / Gold / Gov Bonds), and sends Telegram notifications
with rebalancing recommendations.

**This tool never executes trades.** All recommendations are advisory.

## Features

- **Hourly signal checks** — Monitors portfolio alignment, alerts on threshold
  breaches and cycle inversions
- **Monthly PAC redistribution** — On the 14th, calculates optimal savings plan
  volumes from available balance
- **Telegram bot** — `/status`, `/rebalance`, `/redistribute` commands with
  inline keyboards
- **Serverless** — Runs on Cloud Run with scale-to-zero (~$0/month idle)

## Architecture

```
Telegram API ──POST /webhook──▶ ┌────────────────────┐
                                │  Starlette ASGI    │
Cloud Scheduler ──POST /jobs──▶ │  (Cloud Run)       │──▶ TR WebSocket API
                                │                    │
                                │  /health           │
                                └────────────────────┘
```

## Local Development

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [just](https://github.com/casey/just) task runner

### Setup

```bash
# Clone and install dependencies
git clone <repo-url>
cd trade-republic-pac
uv sync

# Copy and fill environment variables
cp .env.example .env
# Edit .env with your credentials

# Run locally
just run

# Run checks
just validate
```

### Available Commands

```bash
just lint        # Run ruff linter
just format      # Auto-format code
just typecheck   # Run mypy
just test        # Run pytest
just validate    # All checks (lint + typecheck + test)
just run         # Run the application
```

## Deployment

### GCP Setup (one-time)

1. **Create GCP project** and enable APIs:
   ```bash
   gcloud services enable \
     run.googleapis.com \
     artifactregistry.googleapis.com \
     secretmanager.googleapis.com \
     cloudscheduler.googleapis.com
   ```

2. **Create Artifact Registry repository:**
   ```bash
   gcloud artifacts repositories create pac \
     --repository-format=docker \
     --location=REGION
   ```

3. **Create secrets** in Secret Manager:
   ```bash
   just setup-secrets PROJECT_ID
   # Then set each secret value:
   echo -n 'VALUE' | gcloud secrets versions add SECRET_NAME --data-file=-
   ```

4. **Set up Workload Identity Federation** for GitHub Actions
   (see [GCP docs](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines))

5. **Create Cloud Scheduler jobs:**
   ```bash
   just setup-scheduler PROJECT_ID REGION https://your-service.run.app
   ```

6. **Set Telegram webhook** — handled automatically by the app on startup
   when `PAC_WEBHOOK_URL` is set.

### CI/CD

- **PRs**: Lint + typecheck + test (GitHub Actions)
- **Push to main**: Automated deploy to Cloud Run

### GitHub Actions Configuration

**Repository secrets:**
- `GCP_WIF_PROVIDER` — Workload Identity Provider resource name
- `GCP_SA_EMAIL` — Service account email

**Repository variables:**
- `GCP_PROJECT_ID` — GCP project ID
- `GCP_REGION` — GCP region (e.g. `europe-west1`)

## Configuration

All configuration via environment variables with `PAC_` prefix.
See `.env.example` for the full list.

| Variable                 | Required | Default  | Description                   |
| ------------------------ | -------- | -------- | ----------------------------- |
| `PAC_TR_PHONE_NUMBER`    | Yes      | —        | TR account phone number       |
| `PAC_TR_PIN`             | Yes      | —        | TR account PIN                |
| `PAC_TELEGRAM_BOT_TOKEN` | Yes      | —        | Telegram bot API token        |
| `PAC_TELEGRAM_CHAT_ID`   | Yes      | —        | Telegram chat ID              |
| `PAC_WEBHOOK_SECRET`     | Yes      | —        | Webhook auth secret           |
| `PAC_JOB_SECRET`         | Yes      | —        | Cloud Scheduler auth secret   |
| `PAC_WEBHOOK_URL`        | No       | `""`     | Public webhook URL            |
| `PAC_TARGET_STOCKS_PCT`  | No       | `70`     | Stock allocation target %     |
| `PAC_TARGET_GOLD_PCT`    | No       | `15`     | Gold allocation target %      |
| `PAC_TARGET_BONDS_PCT`   | No       | `15`     | Bond allocation target %      |
| `PAC_PAC_MONTHLY_BUDGET` | No       | `500.00` | Monthly investment budget EUR |

## License

Private — not for distribution.