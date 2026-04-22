"""Framework-agnostic backtest pipeline."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pydantic
import structlog
import yaml

from pac.backtester.config import BacktestConfig
from pac.backtester.data.fx import convert_to_eur
from pac.backtester.data.models import DataRequest, PriceSeries
from pac.backtester.data.provider import MarketDataProvider
from pac.backtester.data.proxy_quality import assess_proxy_quality
from pac.backtester.engine.simulator import (
    SimulationResult,
    collect_indicator_meta,
)
from pac.backtester.metrics.report import compute_report
from pac.backtester.results.aggregation import build_run_result
from pac.backtester.results.models import RunResult
from pac.backtester.results.store import ResultStore
from pac.backtester.strategies.discovery import discover_strategies
from pac.config.loader import load_config
from pac.config.models import AssetConfig, Settings
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry

__all__ = ["PipelineError", "ProgressCallback", "run_pipeline"]

log = structlog.get_logger()


class PipelineError(Exception):
    """Raised when the backtest pipeline fails at any step.

    Attributes:
        step: Human-readable name of the failing step.
        detail: Underlying error message.
    """

    def __init__(self, step: str, detail: str) -> None:
        self.step = step
        self.detail = detail
        super().__init__(f"[{step}] {detail}")


ProgressCallback = Callable[[int, int], None]
"""Signature: (current_iteration, total_iterations) -> None."""


def run_pipeline(
    config: BacktestConfig,
    config_path: Path,
    *,
    seed: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> tuple[RunResult, Path]:
    """Run a full backtest pipeline.

    Steps:
      1. Load settings from YAML
      2. Validate all assets have tickers
      3. Fetch market data
      4. Load signal registry
      5. Discover + instantiate strategy
      6. Run MC simulation (calls on_progress after each iteration)
      7. Compute metrics report
      8. Build RunResult
      9. Save to ResultStore

    Args:
        config: Validated backtest configuration.
        config_path: Path to pac.yaml.
        seed: Optional RNG seed for reproducibility.
        on_progress: Called after each MC iteration with (current, total).

    Returns:
        Tuple of (RunResult, path to saved JSON).

    Raises:
        PipelineError: On any fatal step failure.
    """
    # Step 1: Load settings
    try:
        settings = load_config(config_path)
    except FileNotFoundError as e:
        raise PipelineError("config", f"Config not found: {e}") from e
    except yaml.YAMLError as e:
        raise PipelineError("config", f"Config YAML is invalid: {e}") from e
    except ValueError as e:
        raise PipelineError("config", f"Config invalid: {e}") from e

    # Step 2: Validate tickers
    missing = [a for a in settings.assets if not a.ticker]
    if missing:
        names = ", ".join(a.id for a in missing)
        raise PipelineError(
            "tickers",
            f"Assets missing 'ticker' field: {names}\n"
            "Add 'ticker: SWRD.SW' to each asset in pac.yaml.",
        )

    # Step 3: Fetch market data
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        provider = MarketDataProvider()
        assets_with_tickers = [a for a in settings.assets if a.ticker]

        def _fetch_asset(a: AssetConfig) -> tuple[str, PriceSeries]:
            series = provider.fetch_with_proxy(
                ticker=a.ticker,  # type: ignore[arg-type]
                start=config.start_date,
                end=config.end_date,
                proxy_chain=a.proxy_chain or None,
                primary_currency=a.currency,
            )
            return a.ticker, series  # type: ignore[return-value]

        price_data: dict[str, PriceSeries] = {}
        if len(assets_with_tickers) <= 1:
            for a in assets_with_tickers:
                ticker, series = _fetch_asset(a)
                price_data[ticker] = series
        else:
            max_workers = min(len(assets_with_tickers), 8)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_fetch_asset, a): a for a in assets_with_tickers}
                for future in as_completed(futures):
                    ticker, series = future.result()
                    price_data[ticker] = series
    except ImportError as e:
        raise PipelineError(
            "market_data",
            "Backtester requires backtest deps. Install with: uv sync --group backtest",
        ) from e
    except Exception as e:
        raise PipelineError(
            "market_data",
            f"Failed to fetch market data: {e}\n"
            "Check network connectivity and ticker symbols.",
        ) from e

    # Step 3b: Validate proxy quality
    _check_proxy_quality(settings, provider)

    # Step 4: Load signal registry
    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)

    # Step 5: Discover and instantiate strategy
    available = discover_strategies()
    if config.strategy not in available:
        raise PipelineError(
            "strategy",
            f"Unknown strategy '{config.strategy}'.\n"
            f"Available: {', '.join(sorted(available))}",
        )

    strategy_cls = available[config.strategy]
    try:
        params = strategy_cls.params_model.model_validate(
            config.strategy_params,
        )
    except pydantic.ValidationError as e:
        raise PipelineError(
            "strategy",
            f"Invalid strategy params:\n{e}",
        ) from e
    strategy = strategy_cls(params)

    # Step 6: Run MC simulation (parallel for N>1, in-process for N=1)
    from pac.backtester.engine.simulator import run_iterations_parallel

    iterations = run_iterations_parallel(
        config,
        settings,
        price_data,
        registry,
        strategy,
        seed=seed,
        on_progress=on_progress,
    )

    # Step 7: Compute metrics report
    sim_result = SimulationResult(config=config, iterations=iterations)
    try:
        report = compute_report(
            sim_result,
            settings,
            price_data,
            rng_seed=seed,
        )
    except Exception as e:
        raise PipelineError(
            "metrics",
            f"Metrics computation failed: {e}",
        ) from e

    # Step 8: Build RunResult
    try:
        indicator_meta = collect_indicator_meta(settings.signals, registry)
        strategy_event_meta = strategy.event_meta()
        run_result = build_run_result(
            report,
            indicator_meta=indicator_meta,
            strategy_event_meta=strategy_event_meta,
        )
    except ValueError as e:
        raise PipelineError(
            "aggregation",
            f"Failed to build run result (no completed iterations?): {e}",
        ) from e

    # Step 9: Save to ResultStore
    path = ResultStore().save(run_result)

    return run_result, path


def _check_proxy_quality(
    settings: Settings,
    provider: MarketDataProvider,
) -> None:
    """Validate proxy quality for all assets with proxy chains."""
    quality_warnings: list[str] = []
    for a in settings.assets:
        if not a.proxy_chain or a.ticker is None:
            continue
        chain_tickers = [spec.ticker for spec in a.proxy_chain] + [a.ticker]
        for idx in range(len(chain_tickers) - 1):
            proxy_t = chain_tickers[idx]
            target_t = chain_tickers[idx + 1]
            handoff = a.proxy_chain[idx].end
            overlap_start = handoff - timedelta(days=365)
            overlap_end = handoff + timedelta(days=90)
            try:
                proxy_data = provider.fetch(
                    DataRequest(
                        ticker=proxy_t,
                        start=overlap_start,
                        end=overlap_end,
                    )
                )
                target_data = provider.fetch(
                    DataRequest(
                        ticker=target_t,
                        start=overlap_start,
                        end=overlap_end,
                    )
                )
                spec = a.proxy_chain[idx]
                if spec.currency and spec.currency != "EUR":
                    proxy_data = convert_to_eur(
                        proxy_data, spec.currency, provider.fetch
                    )
                next_currency = (
                    a.proxy_chain[idx + 1].currency
                    if idx + 1 < len(a.proxy_chain)
                    else a.currency
                )
                if next_currency and next_currency != "EUR":
                    target_data = convert_to_eur(
                        target_data, next_currency, provider.fetch
                    )

                report = assess_proxy_quality(proxy_data, target_data)
                if report.quality != "good":
                    warning = (
                        f"  ⚠ {a.id}: {proxy_t} → {target_t} "
                        f"— {report.quality.upper()}\n"
                        f"    Correlation: {report.correlation:.3f}, "
                        f"Vol ratio: {report.vol_ratio:.2f}, "
                        f"Overlap: {report.overlap_days} days\n"
                    )
                    for issue in report.issues:
                        warning += f"    • {issue}\n"
                    quality_warnings.append(warning)
            except Exception:
                quality_warnings.append(
                    f"  ⚠ {a.id}: {proxy_t} → {target_t} — "
                    f"Could not validate (data fetch failed)\n"
                )

    if not quality_warnings:
        return

    print("\n" + "=" * 60)
    print("PROXY QUALITY WARNINGS")
    print("=" * 60)
    for w in quality_warnings:
        print(w)
    print("These warnings indicate proxy data may not accurately")
    print("represent the target asset. Results should be interpreted")
    print("with caution.\n")

    if sys.stdin.isatty():
        response = input("Continue with these proxies? [y/N] ").strip().lower()
        if response not in ("y", "yes"):
            raise PipelineError(
                "proxy_validation",
                "Aborted by user due to proxy quality warnings.",
            )
    else:
        log.warning("proxy_quality_warnings", warnings=quality_warnings)
