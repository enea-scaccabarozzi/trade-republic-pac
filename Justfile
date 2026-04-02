# Default recipe
default:
    @just --list

# Run ruff linter
lint:
    uv run ruff check src tests

# Auto-format code
format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

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
    docker build -t trade-republic-pac .

# Run Docker container
docker-run:
    docker run --rm --env-file .env trade-republic-pac
