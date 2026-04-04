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
    uv run ruff check src tests

# Auto-format code
format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Check formatting without modifying files
format-check:
    uv run ruff format --check src tests

# Run mypy type checker
typecheck:
    uv run mypy src

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

# Validate pac.yaml configuration
validate-config *args:
    uv run python scripts/validate_config.py {{ args }}
