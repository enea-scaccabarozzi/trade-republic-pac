"""Consolidation quick-test: DriftDCA strategy vs baseline.

Phase 2 (Consolidation) — Script 1 of 1.

Runs a deterministic single-iteration simulation comparing DriftDCA
against the baseline, then sweeps across all three adjustment formulas
and key parameter values. Results are ranked by TWRR delta to identify
the most promising parameter configurations.

Sweep matrix:
  adjustment_formula: proportional, threshold, stepped
  max_tilt_pct:       0.1, 0.2, 0.3, 0.5, 0.7, 1.0
  threshold_pct:      2.0, 3.0, 5.0, 8.0
    (threshold_pct only relevant for threshold/stepped formulas;
     proportional runs once with default 3.0)

Results saved to: results/consolidation_sweep.json
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EXPERIMENT_DIR.parents[2] / "src"
BASELINE_STRATEGIES = EXPERIMENT_DIR.parents[0] / "001-baseline-dca" / "strategies"
DRIFT_STRATEGIES = EXPERIMENT_DIR / "strategies"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASELINE_STRATEGIES))
sys.path.insert(0, str(DRIFT_STRATEGIES))

from baseline_dca import BaselineDCA, BaselineDCAParams  # noqa: E402
from drift_dca import DriftDCAParams, DriftDCAStrategy  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from pac.backtester.config import BacktestConfig  # noqa: E402
from pac.backtester.engine.simulator import BacktestSimulator, IterationResult  # noqa: E402
from pac.backtester.metrics.returns import equity_to_returns  # noqa: E402
from pac.backtester.metrics.twrr import compute_mwrr, compute_twrr  # noqa: E402
from pac.backtester.research.context import ResearchContext  # noqa: E402
from pac.backtester.strategies.base import BacktestStrategy  # noqa: E402
from pac.rules.discovery import discover_rules  # noqa: E402
from pac.rules.registry import SignalRegistry  # noqa: E402


# ---------------------------------------------------------------------------
# Sweep parameter grid
# ---------------------------------------------------------------------------

FORMULAS = ["proportional", "threshold", "stepped"]
MAX_TILT_VALUES = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
THRESHOLD_VALUES = [2.0, 3.0, 5.0, 8.0]


def _sweep_configs() -> list[dict[str, Any]]:
    """Generate the full parameter sweep grid.

    Proportional formula ignores threshold_pct, so it is run only once
    with the default value (3.0) to avoid redundant simulations.

    Returns:
        List of parameter dicts, each with keys: adjustment_formula,
        max_tilt_pct, threshold_pct.
    """
    configs: list[dict[str, Any]] = []
    for formula in FORMULAS:
        thresholds = [3.0] if formula == "proportional" else THRESHOLD_VALUES
        for tilt in MAX_TILT_VALUES:
            for thresh in thresholds:
                configs.append(
                    {
                        "adjustment_formula": formula,
                        "max_tilt_pct": tilt,
                        "threshold_pct": thresh,
                    }
                )
    return configs


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------


def build_signal_registry(ctx: ResearchContext) -> SignalRegistry:
    """Build a SignalRegistry from context settings.

    Args:
        ctx: Research context carrying application settings.

    Returns:
        Registry populated with any rules referenced in ctx.settings.
    """
    rule_classes = discover_rules()
    registry = SignalRegistry()
    for sig_cfg in ctx.settings.signals:
        if sig_cfg.rule in rule_classes:
            rule_cls = rule_classes[sig_cfg.rule]
            registry.register(rule_cls)
    return registry


def build_backtest_config(ctx: ResearchContext) -> BacktestConfig:
    """Build the shared BacktestConfig for all simulations.

    Args:
        ctx: Research context used for date bounds.

    Returns:
        BacktestConfig with deterministic settings (N=1, seed=42).
    """
    return BacktestConfig(
        strategy="drift_dca",
        strategy_params={},
        start_date=ctx.data_start,
        end_date=ctx.data_end,
        initial_cash=Decimal("0"),
        monthly_contribution={
            "min": Decimal("500"),
            "max": Decimal("700"),
            "distribution": "uniform",
        },
        pac_execution_days=[16],
        settlement_fee=Decimal("1.00"),
        spread_bps=Decimal("10"),
        slippage_days=(0, 0),
        monte_carlo_iterations=1,
        tax_regime="italian",
    )


def run_simulation(
    ctx: ResearchContext,
    strategy: BacktestStrategy[BaseModel],
    config: BacktestConfig,
) -> IterationResult:
    """Run a single deterministic simulation iteration.

    Args:
        ctx: Research context with price data and settings.
        strategy: Instantiated and configured strategy.
        config: BacktestConfig for this run.

    Returns:
        Single IterationResult.
    """
    signal_registry = build_signal_registry(ctx)
    simulator = BacktestSimulator(
        config=config,
        settings=ctx.settings,
        price_data=ctx.ticker_prices,
        signal_registry=signal_registry,
        strategy=strategy,
        rng_seed=42,
    )
    return simulator.run_iteration(0)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_full_metrics(result: IterationResult) -> dict[str, float]:
    """Compute TWRR, MWRR, and quantstats risk metrics for a result.

    Args:
        result: Single iteration result from BacktestSimulator.

    Returns:
        Dict with keys: twrr, mwrr, sharpe, sortino, max_drawdown,
        calmar, volatility, final_value.
    """
    try:
        import quantstats as qs
    except ImportError:
        print("  WARNING: quantstats not available — risk metrics skipped")
        return {
            "twrr": compute_twrr(result),
            "mwrr": compute_mwrr(result, initial_cash=Decimal("0")),
            "final_value": float(result.final_value),
        }

    returns = equity_to_returns(result)
    metrics: dict[str, float] = {
        "twrr": compute_twrr(result),
        "mwrr": compute_mwrr(result, initial_cash=Decimal("0")),
        "final_value": float(result.final_value),
    }
    if not returns.empty:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metrics["sharpe"] = float(qs.stats.sharpe(returns, periods=252))
            metrics["sortino"] = float(qs.stats.sortino(returns, periods=252))
            metrics["max_drawdown"] = float(qs.stats.max_drawdown(returns))
            metrics["calmar"] = float(qs.stats.calmar(returns))
            metrics["volatility"] = float(qs.stats.volatility(returns, periods=252))
    return metrics


def _deltas(
    run_metrics: dict[str, float],
    baseline_metrics: dict[str, float],
) -> dict[str, float]:
    """Compute per-metric deltas vs the baseline.

    Args:
        run_metrics: Metrics for a sweep run.
        baseline_metrics: Metrics for the baseline run.

    Returns:
        Dict mapping metric name to (run - baseline) value.
    """
    return {
        k: run_metrics.get(k, float("nan")) - baseline_metrics.get(k, float("nan"))
        for k in set(run_metrics) | set(baseline_metrics)
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _fmt(value: float, width: int = 10) -> str:
    """Format a float for table display, handling NaN gracefully."""
    if value != value:  # NaN check
        return "n/a".rjust(width)
    return f"{value:+.4f}".rjust(width)


def print_results_table(
    sweep_results: list[dict[str, Any]],
    baseline_metrics: dict[str, float],
) -> None:
    """Print sweep results ranked by TWRR delta descending.

    Args:
        sweep_results: List of result dicts (params + metrics + deltas).
        baseline_metrics: Baseline metrics for reference row.
    """
    ranked = sorted(
        sweep_results,
        key=lambda r: r["deltas"].get("twrr", float("-inf")),
        reverse=True,
    )

    header_fmt = (
        f"  {'Formula':<14} {'Tilt':>6} {'Thresh':>7}"
        f" {'dTWRR':>10} {'dSharpe':>10}"
        f" {'dMax_DD':>10} {'dFinalVal':>12}"
    )
    sep = "  " + "-" * (len(header_fmt) - 2)

    print("\n" + "=" * len(header_fmt))
    print("  SWEEP RESULTS — ranked by TWRR delta vs baseline")
    print("=" * len(header_fmt))
    print(f"\n  Baseline: TWRR={baseline_metrics.get('twrr', float('nan')):.4f}"
          f"  Sharpe={baseline_metrics.get('sharpe', float('nan')):.4f}"
          f"  MaxDD={baseline_metrics.get('max_drawdown', float('nan')):.4f}"
          f"  FinalVal=€{baseline_metrics.get('final_value', float('nan')):,.0f}")
    print()
    print(header_fmt)
    print(sep)

    for row in ranked:
        p = row["params"]
        d = row["deltas"]
        print(
            f"  {p['adjustment_formula']:<14}"
            f" {p['max_tilt_pct']:>6.1f}"
            f" {p['threshold_pct']:>7.1f}"
            f"{_fmt(d.get('twrr', float('nan')))}"
            f"{_fmt(d.get('sharpe', float('nan')))}"
            f"{_fmt(d.get('max_drawdown', float('nan')))}"
            f" {d.get('final_value', float('nan')):>+12,.0f}"
        )

    print(sep)
    print(f"\n  {len(ranked)} configurations evaluated.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point: quick-test + coarse sweep for DriftDCA consolidation."""
    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    print(f"Loading config: {config_path}")
    print("Fetching price data (may take a moment)...")

    ctx = ResearchContext.from_config(
        config_path,
        start_date=date(2005, 1, 1),
        end_date=date(2026, 4, 22),
        packs=["crisis"],
    )
    ctx.register_strategy("baseline_dca", BaselineDCA)
    ctx.register_strategy("drift_dca", DriftDCAStrategy)

    print(f"Data range: {ctx.data_start} to {ctx.data_end}")
    config = build_backtest_config(ctx)

    # ------------------------------------------------------------------
    # Quick test: baseline vs DriftDCA with default params
    # ------------------------------------------------------------------
    print("\n--- Quick test: baseline vs DriftDCA (default params) ---")

    print("Running baseline simulation (N=1, seed=42)...")
    baseline_result = run_simulation(ctx, BaselineDCA(BaselineDCAParams()), config)
    print(
        f"  Baseline: {len(baseline_result.daily_values)} days,"
        f" final value EUR {baseline_result.final_value:,.2f}"
    )

    default_params = DriftDCAParams()
    print(
        f"Running DriftDCA default params"
        f" (formula={default_params.adjustment_formula},"
        f" tilt={default_params.max_tilt_pct},"
        f" threshold={default_params.threshold_pct})..."
    )
    drift_default_result = run_simulation(
        ctx, DriftDCAStrategy(default_params), config
    )
    print(
        f"  DriftDCA: {len(drift_default_result.daily_values)} days,"
        f" final value EUR {drift_default_result.final_value:,.2f}"
    )

    print("Computing metrics...")
    baseline_metrics = compute_full_metrics(baseline_result)
    drift_default_metrics = compute_full_metrics(drift_default_result)
    default_deltas = _deltas(drift_default_metrics, baseline_metrics)

    print(
        f"\n  TWRR delta (default): {default_deltas.get('twrr', float('nan')):+.4f}"
        f"  Sharpe delta: {default_deltas.get('sharpe', float('nan')):+.4f}"
        f"  MaxDD delta: {default_deltas.get('max_drawdown', float('nan')):+.4f}"
    )

    # ------------------------------------------------------------------
    # Coarse parameter sweep
    # ------------------------------------------------------------------
    sweep_grid = _sweep_configs()
    total = len(sweep_grid)
    print(f"\n--- Coarse parameter sweep ({total} configurations) ---")

    sweep_results: list[dict[str, Any]] = []
    for i, params_dict in enumerate(sweep_grid, start=1):
        formula = params_dict["adjustment_formula"]
        tilt = params_dict["max_tilt_pct"]
        thresh = params_dict["threshold_pct"]

        print(
            f"  [{i:>3}/{total}] formula={formula:<12}"
            f" tilt={tilt:.1f}  threshold={thresh:.1f}..."
        )

        params = DriftDCAParams(
            adjustment_formula=formula,
            max_tilt_pct=tilt,
            threshold_pct=thresh,
        )
        result = run_simulation(ctx, DriftDCAStrategy(params), config)
        metrics = compute_full_metrics(result)
        deltas = _deltas(metrics, baseline_metrics)

        sweep_results.append(
            {
                "params": params_dict,
                "metrics": {
                    k: round(v, 6) for k, v in metrics.items() if v == v
                },
                "deltas": {
                    k: round(v, 6) for k, v in deltas.items() if v == v
                },
            }
        )

    # ------------------------------------------------------------------
    # Print ranked table
    # ------------------------------------------------------------------
    print_results_table(sweep_results, baseline_metrics)

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    results_dir = EXPERIMENT_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / "consolidation_sweep.json"

    output_data: dict[str, Any] = {
        "period": f"{ctx.data_start} to {ctx.data_end}",
        "baseline": {
            "final_value": str(baseline_result.final_value),
            "metrics": {
                k: round(v, 6) for k, v in baseline_metrics.items() if v == v
            },
        },
        "quick_test_drift_default": {
            "params": {
                "adjustment_formula": default_params.adjustment_formula,
                "max_tilt_pct": default_params.max_tilt_pct,
                "threshold_pct": default_params.threshold_pct,
            },
            "final_value": str(drift_default_result.final_value),
            "metrics": {
                k: round(v, 6)
                for k, v in drift_default_metrics.items()
                if v == v
            },
            "deltas": {
                k: round(v, 6) for k, v in default_deltas.items() if v == v
            },
        },
        "sweep": sweep_results,
    }

    output_path.write_text(json.dumps(output_data, indent=2))
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
