"""GCP Cloud Run deployment setup.

Guides through project creation, Docker build, Cloud Run deploy, and
Cloud Scheduler job creation.
"""

from __future__ import annotations

import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

# Ensure project root is on sys.path for direct script execution
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import typer  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.prompt import Prompt  # noqa: E402
from rich.table import Table  # noqa: E402

from scripts.setup_utils import (  # noqa: E402
    CacheManager,
    confirm_or_exit,
    console,
    fatal_error,
    print_disclaimer,
    print_success,
    update_env_file,
)

app = typer.Typer(
    name="setup-gcp",
    help="Deploy to GCP Cloud Run with guided setup.",
)

CACHE_NAME = "gcp"
DEFAULT_REGION = "europe-west1"
DEFAULT_SERVICE_NAME = "trade-republic-pac"
ARTIFACT_REPO = "pac"
IMAGE_NAME = "trade-republic-pac"
GHCR_IMAGE = "ghcr.io/enea-scaccabarozzi/trade-republic-pac:latest"

REQUIRED_APIS = [
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
]

# Active gcloud account — set once by _select_account(), used by _run_gcloud().
_ACTIVE_ACCOUNT: str | None = None


# === Subprocess helpers ===


def _run_gcloud(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a gcloud CLI command.

    Args:
        args: Command arguments after 'gcloud'.
        check: If True, exit on non-zero return code.
        capture: If True, capture stdout/stderr.

    Returns:
        CompletedProcess with stdout/stderr as strings.
    """
    account_flag = ["--account", _ACTIVE_ACCOUNT] if _ACTIVE_ACCOUNT else []
    cmd = ["gcloud", *account_flag, *args]
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        fatal_error(
            "gcloud Command Failed",
            f"Command: {' '.join(cmd)}\n\n"
            f"Exit code: {result.returncode}\n"
            f"{result.stderr.strip() if result.stderr else '(no output)'}",
        )
    return result


# === Account selection ===


def _select_account(account: str | None) -> str | None:
    """List authenticated gcloud accounts and let the user pick one.

    Sets the module-level _ACTIVE_ACCOUNT so all subsequent
    _run_gcloud calls use the chosen account.

    Returns:
        The selected account email, or None if none are authenticated.
    """
    global _ACTIVE_ACCOUNT

    if account:
        _ACTIVE_ACCOUNT = account
        console.print(f"[info]Using gcloud account: {account}[/info]")
        return account

    result = _run_gcloud(
        ["auth", "list", "--format=value(account)"],
        check=False,
    )
    accounts = [a.strip() for a in result.stdout.strip().splitlines() if a.strip()]

    if not accounts:
        console.print("[warning]No authenticated gcloud accounts found.[/warning]")
        console.print("Run: gcloud auth login")
        return None

    if len(accounts) == 1:
        _ACTIVE_ACCOUNT = accounts[0]
        console.print(f"[info]Using gcloud account: {accounts[0]}[/info]")
        return accounts[0]

    table = Table(title="Authenticated GCP Accounts")
    table.add_column("#", style="bold")
    table.add_column("Account")
    for i, a in enumerate(accounts, 1):
        table.add_row(str(i), a)
    console.print(table)

    choice = Prompt.ask(
        "Select an account number to use",
        default="1",
        console=console,
    )

    if choice.isdigit() and 1 <= int(choice) <= len(accounts):
        _ACTIVE_ACCOUNT = accounts[int(choice) - 1]
        return _ACTIVE_ACCOUNT

    _ACTIVE_ACCOUNT = choice
    return choice


# === Prerequisite checks ===


def _check_gcloud_installed() -> None:
    """Verify gcloud CLI is installed and accessible."""
    result = subprocess.run(
        ["gcloud", "version"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fatal_error(
            "gcloud Not Found",
            "The Google Cloud CLI (gcloud) is not installed or not in PATH.\n\n"
            "Install it from: https://cloud.google.com/sdk/docs/install\n"
            "Then run: gcloud auth login",
        )


def _check_docker_installed() -> None:
    """Verify Docker is installed and the daemon is running."""
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fatal_error(
            "Docker Not Available",
            "Docker is not installed or the daemon is not running.\n\n"
            "Install Docker: https://docs.docker.com/get-docker/\n"
            "Then ensure the Docker daemon is started.",
        )


def _load_pac_config_raw() -> dict[str, Any]:
    """Load pac.yaml as raw dict (no env interpolation).

    Reads signal definitions (names + schedules) for Cloud Scheduler
    job creation. Does NOT interpolate env vars because secrets may
    not be set in the local shell.
    """
    config_path = Path("pac.yaml")
    if not config_path.exists():
        fatal_error(
            "pac.yaml Not Found",
            "pac.yaml is required for GCP deployment.\n"
            "Copy pac.yaml.example to pac.yaml and configure it first.",
        )
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        fatal_error(
            "Invalid Configuration",
            "pac.yaml must contain a YAML mapping at the top level.",
        )
    return raw


# === GCP project setup ===


def _create_project(project_id: str) -> str:
    """Create a new GCP project and set it as active."""
    with console.status(f"[info]Creating project '{project_id}'...[/info]"):
        _run_gcloud(["projects", "create", project_id])
    _run_gcloud(["config", "set", "project", project_id])
    console.print(f"[success]Project '{project_id}' created.[/success]")
    return project_id


def _ensure_project(project: str | None) -> str:
    """Ensure a GCP project is selected or created.

    If project is provided via CLI flag, validates it exists. Otherwise,
    lists existing projects and lets user select or create one.

    Returns:
        The project ID to use.
    """
    if project:
        with console.status(f"[info]Checking project '{project}'...[/info]"):
            result = _run_gcloud(
                [
                    "projects",
                    "describe",
                    project,
                    "--format=value(projectId)",
                ],
                check=False,
            )
        if result.returncode != 0:
            fatal_error(
                "Project Not Found",
                f"GCP project '{project}' does not exist or you lack access.\n"
                "Check the project ID and your permissions.",
            )
        _run_gcloud(["config", "set", "project", project])
        return project

    # List existing projects
    with console.status("[info]Listing GCP projects...[/info]"):
        result = _run_gcloud(
            ["projects", "list", "--format=value(projectId)"],
        )

    projects = [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]

    if projects:
        table = Table(title="Your GCP Projects")
        table.add_column("#", style="bold")
        table.add_column("Project ID")
        for i, p in enumerate(projects, 1):
            table.add_row(str(i), p)
        console.print(table)

        choice = Prompt.ask(
            "Select a project number, or type a new project ID to create",
            console=console,
        )

        if choice.isdigit() and 1 <= int(choice) <= len(projects):
            selected = projects[int(choice) - 1]
            _run_gcloud(["config", "set", "project", selected])
            return selected

        return _create_project(choice)

    console.print("[warning]No GCP projects found.[/warning]")
    new_id = Prompt.ask("Enter a project ID to create", console=console)
    return _create_project(new_id)


def _check_billing(project_id: str) -> None:
    """Verify billing is enabled for the project."""
    with console.status("[info]Checking billing status...[/info]"):
        result = _run_gcloud(
            [
                "billing",
                "projects",
                "describe",
                project_id,
                "--format=value(billingAccountName)",
            ],
            check=False,
        )

    if result.returncode != 0 or not result.stdout.strip():
        fatal_error(
            "Billing Not Enabled",
            f"Billing is not enabled for project '{project_id}'.\n\n"
            "Enable billing at:\n"
            f"  https://console.cloud.google.com/billing/"
            f"linkedaccount?project={project_id}\n\n"
            "Then re-run this script.",
        )
    console.print("[success]Billing is enabled.[/success]")


def _enable_apis(extra_apis: list[str] | None = None) -> None:
    """Enable required GCP APIs plus any extras."""
    apis = [*REQUIRED_APIS, *(extra_apis or [])]
    with console.status("[info]Enabling required APIs...[/info]"):
        _run_gcloud(["services", "enable", *apis])
    console.print("[success]All required APIs enabled.[/success]")


# === Build & push ===


def _ensure_artifact_repo(project_id: str, region: str) -> str:
    """Create Artifact Registry repo if it doesn't exist.

    Returns:
        The full registry path (REGION-docker.pkg.dev/PROJECT/REPO).
    """
    registry_host = f"{region}-docker.pkg.dev"
    repo_path = f"{registry_host}/{project_id}/{ARTIFACT_REPO}"

    with console.status("[info]Checking Artifact Registry...[/info]"):
        result = _run_gcloud(
            [
                "artifacts",
                "repositories",
                "describe",
                ARTIFACT_REPO,
                f"--location={region}",
                "--format=value(name)",
            ],
            check=False,
        )

    if result.returncode != 0:
        with console.status("[info]Creating Artifact Registry repository...[/info]"):
            _run_gcloud(
                [
                    "artifacts",
                    "repositories",
                    "create",
                    ARTIFACT_REPO,
                    f"--location={region}",
                    "--repository-format=docker",
                    "--description=PAC Docker images",
                ]
            )
        console.print(
            f"[success]Created Artifact Registry repo: {ARTIFACT_REPO}[/success]"
        )

    with console.status("[info]Configuring Docker authentication...[/info]"):
        _run_gcloud(["auth", "configure-docker", registry_host, "--quiet"])

    return repo_path


def _build_and_push(repo_path: str) -> str:
    """Build Docker image locally and push to Artifact Registry.

    Returns:
        The full image URI (with :latest tag).
    """
    image_uri = f"{repo_path}/{IMAGE_NAME}:latest"

    console.print("\n[info]Building Docker image...[/info]")
    build_result = subprocess.run(
        ["docker", "build", "-t", image_uri, "."],
        text=True,
    )
    if build_result.returncode != 0:
        fatal_error(
            "Docker Build Failed",
            "Failed to build the Docker image.\n"
            "Check the Dockerfile and build output above.",
        )

    console.print("[info]Pushing image to Artifact Registry...[/info]")
    push_result = subprocess.run(
        ["docker", "push", image_uri],
        text=True,
    )
    if push_result.returncode != 0:
        fatal_error(
            "Docker Push Failed",
            f"Failed to push image to {image_uri}.\n"
            "Check Docker authentication and try again.",
        )

    console.print(f"[success]Image pushed: {image_uri}[/success]")
    return image_uri


# === Environment variables ===


def _collect_env_vars() -> dict[str, str]:
    """Collect environment variable values for the Cloud Run service.

    Reads cached setup results from .pac/tr.json and .pac/telegram.json
    and prompts for any missing values.

    Returns:
        Dict of env var name -> value for --env-vars-file.
    """
    env_vars: dict[str, str] = {}

    # Job secret — always prompt (sensitive, never cached in plaintext)
    job_secret = Prompt.ask(
        "PAC_JOB_SECRET (HMAC secret for job auth headers)",
        console=console,
    )
    env_vars["PAC_JOB_SECRET"] = job_secret

    # TR credentials from cache or prompt
    tr_cache = CacheManager("tr").load()
    if tr_cache:
        env_vars["TR_PHONE_NUMBER"] = tr_cache.get("phone_number", "")
        console.print(
            f"[info]Using TR phone from cache: {env_vars['TR_PHONE_NUMBER']}[/info]"
        )
    else:
        env_vars["TR_PHONE_NUMBER"] = Prompt.ask(
            "TR_PHONE_NUMBER",
            console=console,
        )

    # TR_PIN — always prompt (never cached)
    env_vars["TR_PIN"] = Prompt.ask("TR_PIN", password=True, console=console)

    # Telegram credentials from cache or prompt
    tg_cache = CacheManager("telegram").load()
    if tg_cache:
        for key in ("bot_token", "chat_id"):
            env_key = f"TELEGRAM_{key.upper()}"
            val = tg_cache.get(key, "")
            if val:
                env_vars[env_key] = str(val)
                console.print(f"[info]Using {env_key} from cache[/info]")

    for env_key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if env_key not in env_vars or not env_vars[env_key]:
            env_vars[env_key] = Prompt.ask(env_key, console=console)

    return env_vars


def _write_env_file(env_vars: dict[str, str]) -> Path:
    """Write env vars to a temporary YAML file for --env-vars-file.

    Uses NamedTemporaryFile with delete=False so the caller can pass
    the path to gcloud and clean up via try/finally.

    Returns:
        Path to the temporary file.
    """
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w",
        suffix=".yaml",
        prefix="pac-env-",
        delete=False,
    )
    try:
        yaml.safe_dump(env_vars, tmp, default_flow_style=False)
        tmp.flush()
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)
        raise
    finally:
        tmp.close()
    return Path(tmp.name)


# === Deploy ===


def _deploy_cloud_run(
    service_name: str,
    image_uri: str,
    region: str,
    env_vars: dict[str, str],
) -> str:
    """Deploy or update Cloud Run service.

    Writes env vars to a temp file and passes --env-vars-file to avoid
    exposing secrets in process arguments / shell history.

    Returns:
        The service URL.
    """
    env_file = _write_env_file(env_vars)
    try:
        with console.status("[info]Deploying to Cloud Run...[/info]"):
            _run_gcloud(
                [
                    "run",
                    "deploy",
                    service_name,
                    f"--image={image_uri}",
                    f"--region={region}",
                    "--platform=managed",
                    "--allow-unauthenticated",
                    "--port=8080",
                    "--memory=512Mi",
                    "--cpu=1",
                    "--min-instances=0",
                    "--max-instances=1",
                    f"--env-vars-file={env_file}",
                    "--quiet",
                ]
            )
    finally:
        env_file.unlink(missing_ok=True)

    # Get service URL
    with console.status("[info]Fetching service URL...[/info]"):
        result = _run_gcloud(
            [
                "run",
                "services",
                "describe",
                service_name,
                f"--region={region}",
                "--format=value(status.url)",
            ]
        )

    service_url = result.stdout.strip()
    if not service_url:
        fatal_error(
            "Deploy Failed",
            "Could not retrieve service URL after deployment.",
        )

    console.print(f"[success]Deployed: {service_url}[/success]")
    return service_url


def _update_webhook_env(
    service_name: str,
    service_url: str,
    region: str,
    env_vars: dict[str, str],
) -> None:
    """Update Cloud Run env vars with the webhook URL.

    Merges existing env vars with webhook URL and secret, then performs
    a service update. Uses --env-vars-file via a temp file to avoid
    exposing secrets in process arguments.
    """
    webhook_url = f"{service_url}/webhook"

    webhook_secret = env_vars.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not webhook_secret:
        webhook_secret = secrets.token_urlsafe(32)
        console.print("[info]Generated TELEGRAM_WEBHOOK_SECRET[/info]")

    # Merge all env vars + webhook vars for the update
    all_vars = {
        **env_vars,
        "TELEGRAM_WEBHOOK_URL": webhook_url,
        "TELEGRAM_WEBHOOK_SECRET": webhook_secret,
    }

    env_file = _write_env_file(all_vars)
    try:
        with console.status("[info]Updating webhook environment variables...[/info]"):
            _run_gcloud(
                [
                    "run",
                    "services",
                    "update",
                    service_name,
                    f"--region={region}",
                    f"--env-vars-file={env_file}",
                    "--quiet",
                ]
            )
    finally:
        env_file.unlink(missing_ok=True)

    console.print(f"[success]Webhook URL set: {webhook_url}[/success]")


def _register_telegram_webhook(
    service_name: str,
    service_url: str,
    region: str,
    env_vars: dict[str, str],
) -> None:
    """Register webhook with Telegram API and update Cloud Run env vars.

    Reads bot_token from .pac/telegram.json, registers the webhook
    with Telegram, updates the telegram cache and .env, then updates
    the Cloud Run service env vars.

    Falls back to updating Cloud Run env vars only if no telegram
    cache exists.
    """
    tg_cache_mgr = CacheManager("telegram")
    tg_data = tg_cache_mgr.load()

    if not tg_data or not tg_data.get("bot_token"):
        console.print(
            "[warning]No Telegram cache found — skipping"
            " webhook registration.\n"
            "Run 'just setup-telegram' to set up the"
            " bot first.[/warning]"
        )
        _update_webhook_env(service_name, service_url, region, env_vars)
        return

    bot_token: str = tg_data["bot_token"]
    webhook_url = f"{service_url.rstrip('/')}/webhook"
    webhook_secret = secrets.token_hex(32)

    # Register with Telegram Bot API
    from scripts.setup_telegram import _register_webhook

    _register_webhook(bot_token, webhook_url, webhook_secret)

    # Update telegram cache with webhook keys
    cache_data = {k: v for k, v in tg_data.items() if not k.startswith("_")}
    cache_data["webhook_url"] = webhook_url
    cache_data["webhook_secret"] = webhook_secret
    tg_cache_mgr.save(cache_data)

    # Update .env with webhook keys
    update_env_file(
        {
            "TELEGRAM_WEBHOOK_URL": webhook_url,
            "TELEGRAM_WEBHOOK_SECRET": webhook_secret,
        }
    )

    # Update Cloud Run env vars
    merged_env = {
        **env_vars,
        "TELEGRAM_WEBHOOK_URL": webhook_url,
        "TELEGRAM_WEBHOOK_SECRET": webhook_secret,
    }
    _update_webhook_env(service_name, service_url, region, merged_env)


# === Cloud Scheduler ===


def _setup_scheduler(
    service_url: str,
    region: str,
    job_secret: str,
    raw_config: dict[str, Any],
) -> list[str]:
    """Create Cloud Scheduler jobs for each signal in pac.yaml.

    Reads signal definitions from the raw YAML config. Creates HTTP
    jobs that POST to the Cloud Run signal dispatch endpoint.

    Returns:
        List of created scheduler job names.
    """
    signals: list[dict[str, Any]] = raw_config.get("signals", [])
    if not signals:
        console.print(
            Panel(
                "[bold yellow]No signals defined in pac.yaml!"
                "[/bold yellow]\n\n"
                "Cloud Scheduler jobs were not created because there"
                " are no signals\nconfigured. To add signals:\n\n"
                "  1. Edit pac.yaml and add entries under 'signals:'\n"
                "  2. Re-run this script with --override to create "
                "scheduler jobs",
                title="⚠️  No Signals Configured",
                border_style="yellow",
            )
        )
        return []

    created_jobs: list[str] = []

    for signal in signals:
        name = signal.get("name", "")
        schedule = signal.get("schedule", "")
        if not name or not schedule:
            console.print(
                f"[warning]Skipping signal with missing "
                f"name/schedule: {signal}[/warning]"
            )
            continue

        job_name = f"pac-signal-{name}"
        uri = f"{service_url}/jobs/signal/{name}"

        # Delete existing job if present (idempotent re-deploy)
        _run_gcloud(
            [
                "scheduler",
                "jobs",
                "delete",
                job_name,
                f"--location={region}",
                "--quiet",
            ],
            check=False,
        )

        with console.status(f"[info]Creating scheduler job: {job_name}...[/info]"):
            _run_gcloud(
                [
                    "scheduler",
                    "jobs",
                    "create",
                    "http",
                    job_name,
                    f"--schedule={schedule}",
                    f"--uri={uri}",
                    "--http-method=POST",
                    f"--headers=X-Job-Secret={job_secret}",
                    f"--location={region}",
                    "--time-zone=UTC",
                    "--quiet",
                ]
            )

        console.print(f"[success]Created scheduler job: {job_name}[/success]")
        created_jobs.append(job_name)

    return created_jobs


# === Main command ===


def _build_cost_disclaimer(
    registry: str,
    signal_count: int,
) -> str:
    """Build the dynamic cost disclaimer text."""
    if registry == "ghcr":
        registry_label = "GHCR (ghcr.io)"
        image_steps = "• Pull pre-built Docker image from GitHub Container Registry\n"
    else:
        registry_label = "Artifact Registry"
        image_steps = "• Build and push a Docker image to Artifact Registry\n"

    # Scheduler cost estimate
    free_jobs = 3
    if signal_count <= free_jobs:
        scheduler_cost = "$0.00/month"
    else:
        paid = signal_count - free_jobs
        scheduler_cost = f"${paid * 0.10:.2f}/month"

    cost_lines = (
        f"Based on your pac.yaml configuration:\n"
        f"• {signal_count} signal(s) detected "
        f"→ {signal_count} Cloud Scheduler job(s) will be created\n"
        f"• Cloud Run: free tier covers ~2M requests/month\n"
        f"• Cloud Scheduler: 3 free jobs; you have {signal_count}"
        f" → estimated cost: {scheduler_cost}\n"
    )
    if registry == "artifact-registry":
        cost_lines += "• Artifact Registry: 0.5 GB free storage\n"

    return (
        f"This script will:\n"
        f"• Create or select a GCP project\n"
        f"• Enable Cloud Run and Cloud Scheduler APIs\n"
        f"{image_steps}"
        f"• Deploy a Cloud Run service\n"
        f"• Create Cloud Scheduler jobs for signal dispatch\n\n"
        f"[bold]Registry mode:[/bold] {registry_label}\n\n"
        f"[bold]Potential costs:[/bold]\n"
        f"{cost_lines}\n"
        f"See https://cloud.google.com/pricing for details.\n\n"
        f"[bold]Security notes:[/bold]\n"
        f"• The Cloud Run service will be [bold]publicly accessible"
        f"[/bold] (required for Telegram webhook delivery). "
        f"Authentication is enforced at the application level via "
        f"HMAC headers.\n"
        f"• Cloud Scheduler job secrets (X-Job-Secret header) may "
        f"appear in GCP audit logs. These logs are only accessible "
        f"to project admins who already have access to the secrets."
    )


@app.command()
def setup(
    project: str | None = typer.Option(None, help="GCP project ID"),
    region: str | None = typer.Option(None, help="GCP region (default: europe-west1)"),
    service_name: str | None = typer.Option(
        None, "--service-name", help="Cloud Run service name"
    ),
    account: str | None = typer.Option(
        None, "--account", help="GCP account (email) to use"
    ),
    override: bool = typer.Option(False, "--override", help="Re-run even if cached"),
    registry: str = typer.Option(
        "ghcr",
        "--registry",
        help="Container registry: ghcr (default) or artifact-registry",
    ),
) -> None:
    """Deploy the application to GCP Cloud Run."""
    if registry not in ("ghcr", "artifact-registry"):
        fatal_error(
            "Invalid Registry",
            f"Unknown registry '{registry}'. Choose 'ghcr' or 'artifact-registry'.",
        )

    cache = CacheManager(CACHE_NAME)

    # ── Check cache ──
    cached = cache.check_cache(override=override)
    if cached is not None:
        return

    # ── Prerequisites (before disclaimer so we can read config) ──
    _check_gcloud_installed()
    _select_account(account)
    if registry == "artifact-registry":
        _check_docker_installed()
    raw_config = _load_pac_config_raw()

    # ── Count signals for cost estimate ──
    signals = raw_config.get("signals", [])
    signal_count = len([s for s in signals if s.get("name") and s.get("schedule")])

    # ── Disclaimer (after config load so costs are dynamic) ──
    print_disclaimer(
        "GCP Deployment",
        _build_cost_disclaimer(registry, signal_count),
    )
    confirm_or_exit()

    # ── Region ──
    if region is None:
        region = Prompt.ask(
            "GCP region",
            default=DEFAULT_REGION,
            console=console,
        )

    # ── Service name ──
    if service_name is None:
        service_name = Prompt.ask(
            "Cloud Run service name",
            default=DEFAULT_SERVICE_NAME,
            console=console,
        )

    # ── Project setup ──
    project_id = _ensure_project(project)
    _check_billing(project_id)

    if registry == "artifact-registry":
        _enable_apis(extra_apis=["artifactregistry.googleapis.com"])
    else:
        _enable_apis()

    # ── Image: GHCR or Artifact Registry ──
    if registry == "ghcr":
        image_uri = GHCR_IMAGE
        console.print(f"[success]Using GHCR image: {image_uri}[/success]")
    else:
        repo_path = _ensure_artifact_repo(project_id, region)
        image_uri = _build_and_push(repo_path)

    # ── Save cache (after image resolution) ──
    cache_data: dict[str, Any] = {
        "project_id": project_id,
        "region": region,
        "service_name": service_name,
        "image_uri": image_uri,
        "registry": registry,
    }
    if registry == "artifact-registry":
        cache_data["artifact_repo"] = ARTIFACT_REPO
    cache.save(cache_data)

    # ── Collect env vars ──
    env_vars = _collect_env_vars()

    # ── Deploy ──
    service_url = _deploy_cloud_run(service_name, image_uri, region, env_vars)

    # ── Save cache (after Cloud Run deploy) ──
    cache_data["service_url"] = service_url
    cache.save(cache_data)

    # ── Webhook URL ──
    _register_telegram_webhook(service_name, service_url, region, env_vars)

    # ── Scheduler ──
    job_secret = env_vars.get("PAC_JOB_SECRET", "")
    scheduler_jobs = _setup_scheduler(service_url, region, job_secret, raw_config)

    # ── Save cache (final — with scheduler jobs) ──
    cache_data["scheduler_jobs"] = scheduler_jobs
    cache.save(cache_data)

    print_success(
        "GCP Deployment Complete",
        f"Project:  {project_id}\n"
        f"Region:   {region}\n"
        f"Service:  {service_url}\n"
        f"Image:    {image_uri}\n"
        f"Jobs:     "
        f"{', '.join(scheduler_jobs) if scheduler_jobs else '(none)'}"
        f"\n\n"
        f"Cache saved to [cyan]{cache.path}[/cyan]",
    )


if __name__ == "__main__":
    app()
