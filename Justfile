# Default recipe
default:
    @just --list

# Install dependencies
sync:
    uv sync

# Install git hooks (pre-commit, commit-msg, pre-push)
hooks-install:
    uv run pre-commit install --hook-type commit-msg --hook-type pre-commit --hook-type pre-push

# Run ruff linter
lint:
    uv run ruff check src tests scripts

# Auto-format code
format:
    uv run ruff format src tests scripts
    uv run ruff check --fix src tests scripts

# Check formatting without modifying files
format-check:
    uv run ruff format --check src tests scripts

# Run mypy type checker
typecheck:
    uv run mypy src scripts

# Run tests
test *args:
    uv run pytest {{ args }}

# Run all checks (lint + typecheck + test)
validate: lint typecheck test

# Run the application
run:
    uv run python -m pac

# Build Docker image
docker-build:
    docker build -t ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest .

# Run Docker container
docker-run:
    docker run --rm --env-file .env ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest

# Development scaffolding

# Scaffold a new signal rule
new-rule name:
    uv run python scripts/scaffold_rule.py {{ name }}

# Scaffold a new delivery channel
new-channel name:
    uv run python scripts/scaffold_channel.py {{ name }}

# Scaffold a new backtest strategy
new-strategy name:
    uv run python scripts/scaffold_strategy.py {{ name }}

# Validate pac.yaml configuration
validate-config *args:
    uv run python scripts/validate_config.py {{ args }}

# Generate .env from cached setup results (.pac/*.json)
generate-env:
    uv run python -c "from scripts.setup_utils import collect_env_from_caches, update_env_file; update_env_file(collect_env_from_caches())"

# Setup scripts

# Run full guided setup (TR → Telegram → GCP)
setup:
    @echo "═══ Step 1/3: Trade Republic credentials ═══"
    just setup-tr
    @echo ""
    @echo "═══ Step 2/3: Telegram bot setup ═══"
    just setup-telegram --skip-webhook
    @echo ""
    @echo "═══ Step 3/3: GCP Cloud Run deployment ═══"
    just setup-gcp
    @echo ""
    @echo "═══ Generating .env from setup results ═══"
    just generate-env
    @echo ""
    @echo "✅ Setup complete! .env is ready. Run 'just run' to start."

# Set up Trade Republic credentials
setup-tr *args:
    uv run python scripts/setup_tr.py {{ args }}

# Deploy to GCP Cloud Run
setup-gcp *args:
    uv run python scripts/setup_gcp.py {{ args }}

# Set up Telegram bot
setup-telegram *args:
    uv run python scripts/setup_telegram.py {{ args }}

# Register Telegram webhook (standalone, after setup-telegram + setup-gcp)
setup-webhook *args:
    uv run python scripts/setup_telegram.py register-webhook {{ args }}
# Backtester

# Install backtester dependencies
backtest-sync:
    uv sync --group backtest

# Run backtester (interactive mode by default; pass subcommand/flags for batch)
backtest *args:
    uv run python -m pac.backtester {{ args }}

# Run crisis backtest validation (full — ~15 scenarios, 50/200 MC iterations)
backtest-validate:
    uv run python scripts/run_backtest_validation.py

# Run crisis backtest validation (quick smoke test — 10 MC iterations)
backtest-validate-quick:
    uv run python scripts/run_backtest_validation.py --quick

# Dashboard

# Install dashboard dependencies
dashboard-sync:
    uv sync --group backtest --group dashboard

# Start dashboard API server (development)
dashboard-dev:
    uv run python -m pac.backtester dashboard --reload

# Start dashboard (production, with built SPA)
dashboard *args:
    uv run python -m pac.backtester dashboard {{ args }}

# Install dashboard UI dependencies
dashboard-ui-sync:
    cd src/pac/backtester/dashboard && bun install

# Start dashboard UI dev server (Vite, proxies to FastAPI)
dashboard-ui-dev:
    cd src/pac/backtester/dashboard && bun run dev

# Build dashboard UI for production
dashboard-ui-build:
    cd src/pac/backtester/dashboard && bun run build

# Lint + format check dashboard UI
dashboard-ui-lint:
    cd src/pac/backtester/dashboard && bun run lint

# Format dashboard UI
dashboard-ui-format:
    cd src/pac/backtester/dashboard && bun run format

# Type-check dashboard UI
dashboard-ui-typecheck:
    cd src/pac/backtester/dashboard && bun run typecheck

# Run all dashboard UI checks (lint + typecheck)
dashboard-ui-validate: dashboard-ui-lint dashboard-ui-typecheck
    @echo "✅ Dashboard UI validation complete"

# Full development setup: install all deps
dashboard-dev-setup: dashboard-sync dashboard-ui-sync
    @echo "✅ Dependencies installed. Run 'just dashboard-dev' and 'just dashboard-ui-dev' in separate terminals."
