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

# Deploy to Cloud Run (requires gcloud CLI, authenticated)
# Uses Cloud Build (--source) for remote build; CI/CD uses local Docker build + push instead.
deploy project region:
    gcloud run deploy trade-republic-pac \
        --source . \
        --region {{ region }} \
        --project {{ project }} \
        --platform managed

# Create GCP Secret Manager secrets
setup-secrets project:
    @echo "Creating secrets in project {{ project }}..."
    gcloud secrets create tr-phone-number --project {{ project }} --replication-policy=automatic
    gcloud secrets create tr-pin --project {{ project }} --replication-policy=automatic
    gcloud secrets create telegram-bot-token --project {{ project }} --replication-policy=automatic
    gcloud secrets create telegram-chat-id --project {{ project }} --replication-policy=automatic
    gcloud secrets create webhook-secret --project {{ project }} --replication-policy=automatic
    gcloud secrets create webhook-url --project {{ project }} --replication-policy=automatic
    gcloud secrets create job-secret --project {{ project }} --replication-policy=automatic
    @echo "Secrets created. Set values with:"
    @echo "  echo -n 'VALUE' | gcloud secrets versions add SECRET_NAME --data-file=- --project {{ project }}"

# Create Cloud Scheduler jobs
# Note: X-Job-Secret is baked at creation time; re-run after rotating the secret.
setup-scheduler project region service-url:
    gcloud scheduler jobs create http pac-hourly-check \
        --location {{ region }} \
        --project {{ project }} \
        --schedule "0 * * * *" \
        --uri "{{ service-url }}/jobs/hourly-check" \
        --http-method POST \
        --oidc-service-account-email pac-scheduler@{{ project }}.iam.gserviceaccount.com \
        --headers "X-Job-Secret=$(gcloud secrets versions access latest --secret=job-secret --project {{ project }})"
    gcloud scheduler jobs create http pac-monthly-pac \
        --location {{ region }} \
        --project {{ project }} \
        --schedule "0 9 14 * *" \
        --uri "{{ service-url }}/jobs/monthly-pac" \
        --http-method POST \
        --oidc-service-account-email pac-scheduler@{{ project }}.iam.gserviceaccount.com \
        --headers "X-Job-Secret=$(gcloud secrets versions access latest --secret=job-secret --project {{ project }})"
