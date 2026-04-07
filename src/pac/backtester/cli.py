"""Backtester CLI — batch and interactive modes for strategy validation."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import pydantic
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from pac.backtester.config import BacktestConfig
from pac.backtester.data.models import DataRequest
from pac.backtester.data.provider import MarketDataProvider
from pac.backtester.engine.simulator import (
    BacktestSimulator,
    IterationResult,
    SimulationResult,
)
from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import MetricValue, RunResult
from pac.backtester.results.store import ResultStore
from pac.backtester.strategies.discovery import discover_strategies
from pac.config.loader import load_config
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry

try:
    import questionary
except ImportError:
    questionary = None  # type: ignore[assignment]


_VALID_METRICS = frozenset(
    {"sortino", "calmar", "max_drawdown", "cagr", "sharpe", "volatility"}
)
_PCT_METRICS = frozenset({"max_drawdown", "cagr"})
_METRIC_LABELS: dict[str, str] = {
    "sortino": "Sortino",
    "calmar": "Calmar",
    "max_drawdown": "Max Drawdown",
    "cagr": "CAGR",
    "sharpe": "Sharpe",
    "volatility": "Volatility",
}

app = typer.Typer(
    name="pac-backtester",
    help="Signal validation engine — replay historical data against your strategy.",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@app.callback()
def main(ctx: typer.Context) -> None:
    """Launch interactive mode when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        _interactive_mode()


# ── Parsing helpers ───────────────────────────────────────────────────────────


def _parse_slippage(s: str) -> tuple[int, int]:
    """Parse 'min-max' → (min, max). Raises typer.BadParameter on bad format."""
    m = re.fullmatch(r"(\d+)-(\d+)", s.strip())
    if m is None:
        raise typer.BadParameter(
            f"Invalid slippage format '{s}'. Use 'min-max' (e.g. '0-3')."
        )
    lo, hi = int(m.group(1)), int(m.group(2))
    if lo > hi:
        raise typer.BadParameter(
            f"Invalid slippage '{s}': min ({lo}) must be <= max ({hi})."
        )
    return lo, hi


def _parse_metrics(s: str) -> list[str]:
    """Parse comma-separated metric names. Validates each name."""
    names = [n.strip() for n in s.split(",") if n.strip()]
    invalid = [n for n in names if n not in _VALID_METRICS]
    if invalid:
        raise typer.BadParameter(
            f"Unknown metrics: {', '.join(invalid)}. "
            f"Choices: {', '.join(sorted(_VALID_METRICS))}"
        )
    return names


def _parse_pac_days(s: str) -> list[int]:
    """Parse 'day1,day2,...' → [day1, day2, ...]. Validates 1-28 range."""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    days: list[int] = []
    for p in parts:
        if not p.isdigit():
            raise typer.BadParameter(
                f"Invalid PAC day '{p}'. Must be an integer 1-28."
            )
        d = int(p)
        if not 1 <= d <= 28:
            raise typer.BadParameter(
                f"PAC execution day must be 1-28, got {d}."
            )
        days.append(d)
    return days


def _parse_strategy_params(s: str) -> dict[str, Any]:
    """Parse JSON string → dict. Raises typer.BadParameter on invalid JSON."""
    try:
        result = json.loads(s)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(
            f"Invalid JSON for strategy params: {e}"
        ) from e
    if not isinstance(result, dict):
        raise typer.BadParameter("Strategy params must be a JSON object.")
    return result


def _error(msg: str) -> None:
    """Print an error message to stderr."""
    typer.echo(f"Error: {msg}", err=True)


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command()
def run(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to pac.yaml config file.",
        ),
    ] = Path("pac.yaml"),
    strategy: Annotated[
        str,
        typer.Option(
            "--strategy",
            "-s",
            help="Strategy name (use 'strategies' command to list available).",
        ),
    ] = ...,  # type: ignore[assignment]
    start: Annotated[
        datetime,
        typer.Option(
            "--start",
            help="Backtest start date (YYYY-MM-DD).",
            formats=["%Y-%m-%d"],
        ),
    ] = ...,  # type: ignore[assignment]
    end: Annotated[
        datetime | None,
        typer.Option(
            "--end",
            help="Backtest end date (YYYY-MM-DD). Defaults to today.",
            formats=["%Y-%m-%d"],
        ),
    ] = None,
    initial_cash: Annotated[
        float,
        typer.Option("--initial-cash", help="Starting cash balance in EUR."),
    ] = 10000.0,
    monthly_contribution: Annotated[
        float,
        typer.Option(
            "--monthly-contribution", help="Monthly PAC contribution in EUR."
        ),
    ] = 500.0,
    metrics: Annotated[
        str,
        typer.Option(
            "--metrics",
            help=(
                "Comma-separated metrics. "
                "Choices: sortino,calmar,max_drawdown,cagr,sharpe,volatility"
            ),
        ),
    ] = "sortino,calmar,max_drawdown,cagr,sharpe",
    slippage_days: Annotated[
        str,
        typer.Option(
            "--slippage-days",
            help="Human decision latency range as 'min-max' (e.g. 0-3).",
        ),
    ] = "0-3",
    iterations: Annotated[
        int,
        typer.Option("--iterations", help="Monte Carlo iteration count.", min=1),
    ] = 100,
    benchmark: Annotated[
        bool,
        typer.Option(
            "--benchmark/--no-benchmark",
            help="Compare against passive buy-and-hold baseline.",
        ),
    ] = True,
    spread_bps: Annotated[
        float,
        typer.Option(
            "--spread-bps",
            help="Simulated bid/ask spread in basis points.",
        ),
    ] = 10.0,
    settlement_fee: Annotated[
        float,
        typer.Option(
            "--settlement-fee",
            help="Per-order settlement fee in EUR (hard rebalance only).",
        ),
    ] = 1.0,
    pac_days: Annotated[
        str,
        typer.Option(
            "--pac-days",
            help="PAC execution days of month as 'day1,day2,...' (e.g. 2,16).",
        ),
    ] = "2,16",
    strategy_params: Annotated[
        str,
        typer.Option(
            "--strategy-params",
            help=(
                "JSON string of strategy-specific params "
                "(e.g. '{\"threshold_pct\": 5}')."
            ),
        ),
    ] = "{}",
    seed: Annotated[
        int | None,
        typer.Option(
            "--seed",
            help="RNG seed for reproducible Monte Carlo results.",
        ),
    ] = None,
) -> None:
    """Run a backtest in batch mode."""
    slip_min, slip_max = _parse_slippage(slippage_days)
    metrics_list = _parse_metrics(metrics)
    pac_day_list = _parse_pac_days(pac_days)
    params_dict = _parse_strategy_params(strategy_params)

    end_date = end.date() if end is not None else date.today()
    start_date = start.date()

    try:
        bt_config = BacktestConfig(
            strategy=strategy,
            strategy_params=params_dict,
            start_date=start_date,
            end_date=end_date,
            initial_cash=Decimal(str(initial_cash)),
            monthly_contribution=Decimal(str(monthly_contribution)),
            pac_execution_days=pac_day_list,
            settlement_fee=Decimal(str(settlement_fee)),
            spread_bps=Decimal(str(spread_bps)),
            slippage_days=(slip_min, slip_max),
            monte_carlo_iterations=iterations,
            metrics=metrics_list,
            benchmark=benchmark,
        )
    except pydantic.ValidationError as e:
        _error(str(e))
        raise typer.Exit(1) from None

    run_result, path = _run_backtest(bt_config, config, seed)
    _display_run_result(run_result, saved_path=path)


@app.command()
def strategies() -> None:
    """List all available backtest strategies."""
    con = Console()

    try:
        available = discover_strategies()
    except ImportError as e:
        _error(f"Failed to load strategies: {e}")
        raise typer.Exit(1) from None

    con.print(Panel("Available Backtest Strategies", expand=False))
    con.print()

    if not available:
        con.print("No strategies found.")
        return

    table = Table(show_header=True, header_style="bold", show_edge=False)
    table.add_column("Strategy")
    table.add_column("Params Model")
    table.add_column("Description")

    for name in sorted(available):
        cls = available[name]
        params_model_name = cls.params_model.__name__
        doc = (cls.__doc__ or "").strip()
        first_line = doc.splitlines()[0] if doc else "—"
        table.add_row(name, params_model_name, first_line)

    con.print(table)
    con.print(f"\n{len(available)} strategies found.")


@app.command()
def results() -> None:
    """List all saved backtest runs."""
    con = Console()
    con.print(Panel("Saved Backtest Runs", expand=False))
    con.print()

    store = ResultStore()
    run_ids = store.list_runs()

    if not run_ids:
        con.print(
            "No saved backtest runs found. "
            "Run 'pac.backtester run ...' to create one."
        )
        return

    table = Table(show_header=True, header_style="bold", show_edge=False)
    table.add_column("Run ID")
    table.add_column("Strategy")
    table.add_column("Date")
    table.add_column("Final (med)")
    table.add_column("CAGR")

    shown = 0
    for run_id in run_ids:
        try:
            result = store.load(run_id)
        except (ValueError, Exception):
            con.print(
                f"[yellow]Warning: skipping corrupted entry {run_id}[/yellow]"
            )
            continue

        strategy_name = result.config.strategy
        created = result.created_at.strftime("%Y-%m-%d")
        final_val = f"€{result.summary.final_value.median:,.0f}"

        cagr_mv = result.metrics.get("strategy", {}).get("cagr", "—")
        cagr_str = (
            f"{cagr_mv.median * 100:.1f}%"
            if isinstance(cagr_mv, MetricValue)
            else "—"
        )

        table.add_row(run_id, strategy_name, created, final_val, cagr_str)
        shown += 1

    con.print(table)
    con.print(f"\n{shown} results found. Use 'show <run-id>' for details.")


@app.command()
def show(
    run_id: Annotated[str, typer.Argument(help="Run ID to inspect.")],
) -> None:
    """Show detailed results for a saved backtest run."""
    store = ResultStore()
    try:
        result = store.load(run_id)
    except FileNotFoundError:
        _error(
            f"No backtest result found for run ID '{run_id}'.\n"
            "Run 'python -m pac.backtester results' to list available runs."
        )
        raise typer.Exit(1) from None
    except ValueError:
        _error(
            f"Invalid run ID '{run_id}'. "
            "Run 'python -m pac.backtester results' to list available runs."
        )
        raise typer.Exit(1) from None

    saved_path = Path(".pac/backtests") / f"{run_id}.json"
    _display_run_result(result, saved_path=saved_path)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _fmt_metric_value(mv: MetricValue, *, is_pct: bool) -> str:
    """Format a MetricValue with P5-P95 confidence interval."""
    if is_pct:
        return (
            f"{mv.median * 100:.1f}% "
            f"[{mv.p5 * 100:6.1f}% - {mv.p95 * 100:5.1f}%]"
        )
    return f"{mv.median:.2f} [{mv.p5:.2f} - {mv.p95:.2f}]"


def _fmt_benchmark_value(mv: MetricValue, *, is_pct: bool) -> str:
    """Format a benchmark MetricValue (median only)."""
    if is_pct:
        return f"{mv.median * 100:.1f}%"
    return f"{mv.median:.2f}"


def _display_run_result(
    result: RunResult, saved_path: Path | None = None
) -> None:
    """Render a RunResult to the terminal using rich panels and tables."""
    con = Console()
    config = result.config
    slip_min, slip_max = config.slippage_days

    con.print(
        Panel(
            f"{config.start_date} → {config.end_date} · "
            f"{config.monte_carlo_iterations} iterations · "
            f"slippage: {slip_min}-{slip_max} days",
            title=f"Backtest Results: {config.strategy}",
        )
    )

    # Metrics table
    con.print("\n📈 [bold]Performance Metrics[/bold]\n")
    table = Table(show_header=True, header_style="bold", show_edge=False)
    table.add_column("Metric")
    table.add_column("Strategy [P5 - P95]")
    if config.benchmark:
        table.add_column("Benchmark")

    strategy_metrics = result.metrics.get("strategy", {})
    benchmark_metrics = result.metrics.get("benchmark", {})

    for metric_name in config.metrics:
        label = _METRIC_LABELS.get(metric_name, metric_name.title())
        is_pct = metric_name in _PCT_METRICS
        mv = strategy_metrics.get(metric_name)
        if mv is None:
            continue
        row: list[str] = [label, _fmt_metric_value(mv, is_pct=is_pct)]
        if config.benchmark:
            bv = benchmark_metrics.get(metric_name)
            row.append(
                _fmt_benchmark_value(bv, is_pct=is_pct) if bv is not None else "—"
            )
        table.add_row(*row)

    con.print(table)

    # Summary
    con.print("\n💰 [bold]Summary[/bold]\n")
    summary = result.summary
    fv = summary.final_value
    fees = summary.total_fees
    trades = summary.total_trades
    total_return_pct = (
        (fv.median - summary.total_invested) / summary.total_invested * 100
        if summary.total_invested > 0
        else 0.0
    )

    con.print(f" Total Invested:    €{summary.total_invested:,.2f}")
    con.print(
        f" Final Value:       €{fv.median:,.0f}"
        f" [ €{fv.p5:,.0f} - €{fv.p95:,.0f} ]"
    )
    con.print(f" Total Return:      {total_return_pct:+.1f}%")
    con.print(
        f" Total Fees:        €{fees.median:.0f}"
        f" [ €{fees.p5:.0f} - €{fees.p95:.0f} ]"
    )
    con.print(
        f" Total Trades:      {trades.median:.0f}"
        f" [ {trades.p5:.0f} - {trades.p95:.0f} ]"
    )
    con.print(f" PAC Executions:    {summary.total_pac_executions}")
    con.print()

    if saved_path is not None:
        con.print(f"💾 Source: {saved_path}")


def _run_backtest(
    config: BacktestConfig,
    config_path: Path,
    seed: int | None,
) -> tuple[RunResult, Path]:
    """Orchestrate a full backtest run with Rich progress output.

    Steps:
      1. Load settings from YAML
      2. Validate all assets have tickers configured
      3. Load market data (with progress spinner)
      4. Load SignalRegistry from discovered rules
      5. Discover and instantiate strategy
      6. Run simulator (with progress bar over MC iterations)
      7. Compute metrics report
      8. Build RunResult
      9. Save to ResultStore
     10. Return RunResult for display

    Args:
        config: Validated backtest configuration.
        config_path: Path to the pac.yaml config file.
        seed: Optional RNG seed for MC reproducibility.

    Returns:
        Tuple of (RunResult, path to saved JSON).

    Raises:
        typer.Exit(1): On any fatal error (printed to stderr via _error).
    """
    con = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=con,
        transient=True,
    ) as progress:
        # Step 1: Load settings
        task = progress.add_task("Loading config...", total=None)
        try:
            settings = load_config(config_path)
        except FileNotFoundError as e:
            _error(f"Config not found: {e}")
            raise typer.Exit(1) from None
        except yaml.YAMLError as e:
            _error(f"Config YAML is invalid: {e}")
            raise typer.Exit(1) from None
        except ValueError as e:
            _error(f"Config invalid: {e}")
            raise typer.Exit(1) from None
        progress.update(task, completed=1, total=1)

        # Step 2: Validate tickers
        task2 = progress.add_task("Validating asset tickers...", total=None)
        missing = [a for a in settings.assets if not a.ticker]
        if missing:
            names = ", ".join(a.id for a in missing)
            _error(
                f"Assets missing 'ticker' field: {names}\n"
                "Add 'ticker: SWRD.SW' to each asset in pac.yaml."
            )
            raise typer.Exit(1)
        progress.update(task2, completed=1, total=1)

        # Step 3: Load market data
        task3 = progress.add_task("Fetching market data...", total=None)
        requests = [
            DataRequest(
                ticker=ticker,
                start=config.start_date,
                end=config.end_date,
            )
            for a in settings.assets
            if (ticker := a.ticker) is not None
        ]
        try:
            provider = MarketDataProvider()
            price_data = {req.ticker: provider.fetch(req) for req in requests}
        except ImportError:
            _error(
                "Backtester requires backtest deps. "
                "Install with: uv sync --group backtest"
            )
            raise typer.Exit(1) from None
        except Exception as e:
            _error(
                f"Failed to fetch market data: {e}\n"
                "Check network connectivity and ticker symbols."
            )
            raise typer.Exit(1) from None
        progress.update(task3, completed=1, total=1)

        # Step 4: Load signal registry
        rule_classes = discover_rules()
        registry = SignalRegistry()
        for rule_cls in rule_classes.values():
            registry.register(rule_cls)

        # Step 5: Discover and instantiate strategy
        available = discover_strategies()
        if config.strategy not in available:
            _error(
                f"Unknown strategy '{config.strategy}'.\n"
                f"Available: {', '.join(sorted(available))}"
            )
            raise typer.Exit(1)

        strategy_cls = available[config.strategy]
        try:
            params = strategy_cls.params_model.model_validate(
                config.strategy_params
            )
        except pydantic.ValidationError as e:
            _error(f"Invalid strategy params:\n{e}")
            raise typer.Exit(1) from None
        strategy = strategy_cls(params)

        # Step 6: Run simulator with MC progress
        simulator = BacktestSimulator(
            config,
            settings,
            price_data,
            registry,
            strategy,
            rng_seed=seed,
        )
        mc_task = progress.add_task(
            f"Running {config.monte_carlo_iterations} Monte Carlo iterations...",
            total=config.monte_carlo_iterations,
        )
        iterations: list[IterationResult] = []
        for i in range(config.monte_carlo_iterations):
            iterations.append(simulator.run_iteration(i))
            progress.update(mc_task, advance=1)

        # Step 7/8/9: Metrics → report → RunResult → save
        try:
            from pac.backtester.metrics.report import compute_report
        except ImportError:
            _error(
                "Backtester requires backtest deps. "
                "Install with: uv sync --group backtest"
            )
            raise typer.Exit(1) from None

        sim_result = SimulationResult(config=config, iterations=iterations)
        report = compute_report(sim_result, settings, price_data, rng_seed=seed)
        try:
            run_result = build_run_result(report)
        except ValueError as e:
            _error(
                f"Failed to build run result (no completed iterations?): {e}"
            )
            raise typer.Exit(1) from None
        path = ResultStore().save(run_result)

    return run_result, path


def _try_parse_date(s: str) -> date | None:
    """Try to parse a YYYY-MM-DD string. Returns None on failure."""
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def _try_positive_float(s: str) -> bool:
    """Return True if s is a positive float string."""
    try:
        return float(s) > 0
    except ValueError:
        return False


def _try_non_negative_float(s: str) -> bool:
    """Return True if s is a non-negative float string."""
    try:
        return float(s) >= 0
    except ValueError:
        return False


def _try_parse_json(s: str) -> dict[str, Any] | None:
    """Try to parse a JSON object string. Returns None on failure."""
    try:
        result = json.loads(s)
        if isinstance(result, dict):
            return result
        return None
    except json.JSONDecodeError:
        return None


def _interactive_mode() -> None:
    """Run the interactive questionary-based mode."""
    if questionary is None:
        typer.echo(
            "Interactive mode requires questionary.\n"
            "Install with: uv sync --group backtest",
            err=False,
        )
        raise typer.Exit(1)

    try:
        available = discover_strategies()
    except ImportError as e:
        _error(f"Failed to load strategies: {e}")
        raise typer.Exit(1) from None

    strategy_names = sorted(available)

    # 1. Strategy selection
    strategy_answer = questionary.select(
        "Which strategy would you like to run?",
        choices=[*strategy_names, "Cancel"],
    ).ask()
    if strategy_answer is None or strategy_answer == "Cancel":
        raise typer.Exit(0)

    # 2. Config path
    config_answer = questionary.text(
        "Path to pac.yaml config file:",
        default="pac.yaml",
        validate=lambda p: Path(p).exists() or "File not found",
    ).ask()
    if config_answer is None:
        raise typer.Exit(0)

    # 3. Start date
    start_answer = questionary.text(
        "Start date (YYYY-MM-DD):",
        validate=lambda s: (
            _try_parse_date(s) is not None or "Invalid date (YYYY-MM-DD)"
        ),
    ).ask()
    if start_answer is None:
        raise typer.Exit(0)

    # 4. End date
    today_str = date.today().strftime("%Y-%m-%d")
    end_answer = questionary.text(
        "End date (YYYY-MM-DD, or press Enter for today):",
        default=today_str,
        validate=lambda s: (
            _try_parse_date(s) is not None or "Invalid date (YYYY-MM-DD)"
        ),
    ).ask()
    if end_answer is None:
        raise typer.Exit(0)

    # 5. Initial cash
    initial_cash_answer = questionary.text(
        "Initial cash balance (EUR):",
        default="10000",
        validate=lambda s: (
            _try_positive_float(s) or "Must be a positive number"
        ),
    ).ask()
    if initial_cash_answer is None:
        raise typer.Exit(0)

    # 6. Monthly contribution
    monthly_answer = questionary.text(
        "Monthly PAC contribution (EUR):",
        default="500",
        validate=lambda s: (
            _try_non_negative_float(s) or "Must be a non-negative number"
        ),
    ).ask()
    if monthly_answer is None:
        raise typer.Exit(0)

    # 7. Metrics
    metrics_choices = [
        questionary.Choice("sortino", checked=True),
        questionary.Choice("calmar", checked=True),
        questionary.Choice("max_drawdown", checked=True),
        questionary.Choice("cagr", checked=True),
        questionary.Choice("sharpe", checked=True),
        questionary.Choice("volatility", checked=False),
    ]
    metrics_answer: list[str] | None = questionary.checkbox(
        "Which metrics to compute? (Space to toggle, Enter to confirm)",
        choices=metrics_choices,
    ).ask()
    if metrics_answer is None or not metrics_answer:
        raise typer.Exit(0)

    # 8. Slippage days
    slippage_answer = questionary.text(
        "Human decision latency range (min-max days, e.g. 0-3):",
        default="0-3",
        validate=lambda s: (
            re.fullmatch(r"\d+-\d+", s.strip()) is not None
            or "Use format 'min-max' (e.g. 0-3)"
        ),
    ).ask()
    if slippage_answer is None:
        raise typer.Exit(0)

    # 9. Iterations
    iterations_answer = questionary.text(
        "Monte Carlo iterations:",
        default="100",
        validate=lambda s: (
            (s.isdigit() and int(s) >= 1) or "Must be an integer >= 1"
        ),
    ).ask()
    if iterations_answer is None:
        raise typer.Exit(0)

    # 10. Benchmark
    benchmark_answer = questionary.confirm(
        "Compare against passive buy-and-hold benchmark?",
        default=True,
    ).ask()
    if benchmark_answer is None:
        raise typer.Exit(0)

    # 11. Strategy params
    strategy_params_answer = questionary.text(
        "Strategy params as JSON (or press Enter for defaults):",
        default="{}",
        validate=lambda s: (
            _try_parse_json(s) is not None or "Must be valid JSON"
        ),
    ).ask()
    if strategy_params_answer is None:
        raise typer.Exit(0)

    # 12. Confirmation summary
    con = Console()
    con.print("\n[bold]Summary[/bold]")
    con.print(f"  Strategy:      {strategy_answer}")
    con.print(f"  Config:        {config_answer}")
    con.print(f"  Start:         {start_answer}")
    con.print(f"  End:           {end_answer}")
    con.print(f"  Initial cash:  €{initial_cash_answer}")
    con.print(f"  Monthly PAC:   €{monthly_answer}")
    con.print(f"  Metrics:       {', '.join(metrics_answer)}")
    con.print(f"  Slippage:      {slippage_answer}")
    con.print(f"  Iterations:    {iterations_answer}")
    con.print(f"  Benchmark:     {benchmark_answer}")
    con.print(f"  Params:        {strategy_params_answer}")
    con.print()

    confirmed = questionary.confirm(
        "Run backtest with these settings?",
        default=True,
    ).ask()
    if not confirmed:
        raise typer.Exit(0)

    slip_min, slip_max = _parse_slippage(slippage_answer)
    params_dict = _parse_strategy_params(strategy_params_answer)

    try:
        bt_config = BacktestConfig(
            strategy=strategy_answer,
            strategy_params=params_dict,
            start_date=date.fromisoformat(start_answer),
            end_date=date.fromisoformat(end_answer),
            initial_cash=Decimal(str(initial_cash_answer)),
            monthly_contribution=Decimal(str(monthly_answer)),
            slippage_days=(slip_min, slip_max),
            monte_carlo_iterations=int(iterations_answer),
            metrics=metrics_answer,
            benchmark=bool(benchmark_answer),
        )
    except pydantic.ValidationError as e:
        _error(str(e))
        raise typer.Exit(1) from None

    run_result, path = _run_backtest(bt_config, Path(config_answer), None)
    _display_run_result(run_result, saved_path=path)
