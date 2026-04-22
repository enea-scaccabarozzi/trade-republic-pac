"""Validation: full MC, OOS holdout, walk-forward, event analysis, QuantStats.

Produces the definitive baseline numbers for all future experiments.
Builds BacktestSimulator directly to control pac_execution_days=[16].
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT.parents[2] / "src"))
sys.path.insert(0, str(EXPERIMENT_ROOT))

from strategies.baseline_dca import BaselineDCA, BaselineDCAParams

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import BacktestSimulator, IterationResult
from pac.backtester.research.context import ResearchContext
from pac.backtester.strategies.discovery import discover_strategies
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry

EXPERIMENT_DIR = EXPERIMENT_ROOT
RESULTS_DIR = EXPERIMENT_DIR / "results"
ARTIFACTS_DIR = EXPERIMENT_DIR / "artifacts"
START_DATE = date(2005, 1, 1)
END_DATE = date(2026, 4, 22)

CONTRIBUTION = {"min": Decimal("500"), "max": Decimal("700"), "distribution": "uniform"}
INITIAL_CASH = Decimal("10000")


def setup_context() -> ResearchContext:
    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    ctx = ResearchContext.from_config(config_path, start_date=START_DATE, end_date=END_DATE, packs=["crisis"])
    if ctx._strategies is None:
        ctx._strategies = discover_strategies()
    ctx._strategies["baseline_dca"] = BaselineDCA
    return ctx


def build_config(ctx: ResearchContext, **overrides) -> BacktestConfig:
    defaults = {
        "strategy": "baseline_dca",
        "strategy_params": {},
        "start_date": ctx._data_start,
        "end_date": ctx._data_end,
        "initial_cash": INITIAL_CASH,
        "monthly_contribution": CONTRIBUTION,
        "pac_execution_days": [16],
        "settlement_fee": Decimal("1.00"),
        "spread_bps": Decimal("10"),
        "slippage_days": (0, 0),
        "monte_carlo_iterations": 1,
        "tax_regime": "italian",
    }
    defaults.update(overrides)
    return BacktestConfig(**defaults)


def build_signal_registry() -> SignalRegistry:
    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)
    return registry


def run_single(ctx: ResearchContext, config: BacktestConfig, seed: int = 42) -> IterationResult:
    strategy = BaselineDCA(BaselineDCAParams())
    signal_registry = build_signal_registry()
    simulator = BacktestSimulator(
        config=config, settings=ctx.settings,
        price_data=ctx._ticker_price_data,
        signal_registry=signal_registry, strategy=strategy,
        rng_seed=seed,
    )
    return simulator.run_iteration(0)


def run_mc(ctx: ResearchContext, iterations: int = 50, seed: int = 42) -> list[IterationResult]:
    config = build_config(ctx, monte_carlo_iterations=iterations, slippage_days=(0, 3))
    strategy = BaselineDCA(BaselineDCAParams())
    signal_registry = build_signal_registry()
    simulator = BacktestSimulator(
        config=config, settings=ctx.settings,
        price_data=ctx._ticker_price_data,
        signal_registry=signal_registry, strategy=strategy,
        rng_seed=seed,
    )
    results = []
    for i in range(iterations):
        strategy.reset()
        results.append(simulator.run_iteration(i))
    return results


def validate_mc(ctx: ResearchContext) -> dict:
    """Monte Carlo simulation with 50 iterations."""
    print("\n[1/5] Monte Carlo simulation (N=50)...")
    iterations = run_mc(ctx, iterations=50, seed=42)

    final_values = [float(it.final_value) for it in iterations]
    import numpy as np
    p5, median, p95 = np.percentile(final_values, [5, 50, 95])

    all_metrics = {}
    for it in iterations:
        m = ctx.compute_metrics(it, ["sharpe", "cagr", "max_drawdown", "sortino", "calmar"])
        for k, v in m.items():
            all_metrics.setdefault(k, []).append(v)

    metric_bands = {}
    for k, vals in all_metrics.items():
        arr = np.array(vals)
        mp5, mmed, mp95 = np.nanpercentile(arr, [5, 50, 95])
        metric_bands[k] = {"p5": round(mp5, 4), "median": round(mmed, 4), "p95": round(mp95, 4)}

    result = {
        "iterations": len(iterations),
        "final_value": {"p5": round(p5, 2), "median": round(median, 2), "p95": round(p95, 2)},
        "metrics": metric_bands,
    }

    print(f"  Final value: P5={p5:,.0f}  Median={median:,.0f}  P95={p95:,.0f}")
    for k, v in metric_bands.items():
        print(f"  {k:<15} P5={v['p5']:.4f}  Med={v['median']:.4f}  P95={v['p95']:.4f}")

    return result


def validate_oos(ctx: ResearchContext) -> dict:
    """Out-of-sample holdout validation (70/30 split)."""
    print("\n[2/5] Out-of-sample validation (70/30 split)...")
    total_days = (ctx._data_end - ctx._data_start).days
    split_date = ctx._data_start + timedelta(days=int(total_days * 0.7))

    is_config = build_config(ctx, start_date=ctx._data_start, end_date=split_date - timedelta(days=1))
    oos_config = build_config(ctx, start_date=split_date, end_date=ctx._data_end)

    is_result = run_single(ctx, is_config)
    oos_result = run_single(ctx, oos_config)

    is_metrics = ctx.compute_metrics(is_result, ["sharpe", "cagr", "max_drawdown"])
    oos_metrics = ctx.compute_metrics(oos_result, ["sharpe", "cagr", "max_drawdown"])

    primary = "sharpe"
    deg_ratio = oos_metrics[primary] / is_metrics[primary] if is_metrics[primary] != 0 else float("nan")

    result = {
        "split_date": str(split_date),
        "in_sample": {"metrics": {k: round(v, 4) for k, v in is_metrics.items()}, "final_value": float(is_result.final_value)},
        "out_of_sample": {"metrics": {k: round(v, 4) for k, v in oos_metrics.items()}, "final_value": float(oos_result.final_value)},
        "degradation_ratio": round(deg_ratio, 4),
    }

    print(f"  Split date: {split_date}")
    print(f"  IS  sharpe={is_metrics['sharpe']:.4f}  cagr={is_metrics['cagr']:.4f}  maxdd={is_metrics['max_drawdown']:.4f}")
    print(f"  OOS sharpe={oos_metrics['sharpe']:.4f}  cagr={oos_metrics['cagr']:.4f}  maxdd={oos_metrics['max_drawdown']:.4f}")
    print(f"  Degradation ratio: {deg_ratio:.4f}")

    return result


def validate_walk_forward(ctx: ResearchContext) -> dict:
    """Walk-forward validation: expanding IS windows, 5yr OOS steps."""
    print("\n[3/5] Walk-forward validation (10yr IS, 5yr step)...")
    windows = []
    is_end = ctx._data_start + timedelta(days=10 * 365)
    step = timedelta(days=5 * 365)

    while is_end < ctx._data_end:
        oos_end = min(is_end + step, ctx._data_end)
        if (oos_end - is_end).days < 90:
            break
        windows.append((ctx._data_start, is_end, is_end + timedelta(days=1), oos_end))
        is_end = oos_end

    wf_results = []
    oos_sharpes = []
    for is_start, is_end, oos_start, oos_end in windows:
        is_config = build_config(ctx, start_date=is_start, end_date=is_end)
        oos_config = build_config(ctx, start_date=oos_start, end_date=oos_end)
        is_result = run_single(ctx, is_config)
        oos_result = run_single(ctx, oos_config)
        is_m = ctx.compute_metrics(is_result, ["sharpe", "cagr", "max_drawdown"])
        oos_m = ctx.compute_metrics(oos_result, ["sharpe", "cagr", "max_drawdown"])
        oos_sharpes.append(oos_m["sharpe"])
        wf_results.append({
            "is_period": f"{is_start} to {is_end}",
            "oos_period": f"{oos_start} to {oos_end}",
            "is_metrics": {k: round(v, 4) for k, v in is_m.items()},
            "oos_metrics": {k: round(v, 4) for k, v in oos_m.items()},
        })
        print(f"  Window {len(wf_results)}: IS [{is_start}→{is_end}] OOS [{oos_start}→{oos_end}]")
        print(f"    IS  sharpe={is_m['sharpe']:.4f}  OOS sharpe={oos_m['sharpe']:.4f}")

    import statistics
    stability = (statistics.mean(oos_sharpes) / statistics.stdev(oos_sharpes)
                 if len(oos_sharpes) > 1 and statistics.stdev(oos_sharpes) > 0 else float("nan"))

    print(f"  Stability score: {stability:.4f}")
    return {"windows": wf_results, "stability_score": round(stability, 4)}


def validate_events(ctx: ResearchContext) -> dict:
    """Event analysis against crisis calendar."""
    print("\n[4/5] Event analysis (crisis calendar)...")
    config = build_config(ctx)
    result = run_single(ctx, config)

    crises = ctx.calendars["crises"]
    relevant = [e for e in crises.events if e.start <= ctx._data_end and e.end >= ctx._data_start]

    per_event = []
    for event in relevant:
        sub = [dv for dv in result.daily_values if event.start <= dv.date <= event.end]
        if len(sub) >= 2:
            start_val = float(sub[0].total_value)
            end_val = float(sub[-1].total_value)
            ret = (end_val - start_val) / start_val if start_val > 0 else float("nan")
        else:
            ret = float("nan")
        per_event.append({
            "name": event.name,
            "period": f"{event.start} to {event.end}",
            "return": round(ret, 4),
        })
        print(f"  {event.name}: return={ret:+.2%}")

    return {"events": per_event}


def generate_tearsheet(ctx: ResearchContext) -> None:
    """Generate QuantStats HTML tearsheet and save plots."""
    print("\n[5/5] Generating QuantStats tearsheet and plots...")
    config = build_config(ctx)
    result = run_single(ctx, config)

    ARTIFACTS_DIR.mkdir(exist_ok=True)

    try:
        report_path = ctx.quantstats_report(
            result,
            output=str(ARTIFACTS_DIR / "tearsheet.html"),
            title="Baseline DCA 70/15/15",
        )
        print(f"  Tearsheet saved to {report_path}")
    except Exception as e:
        print(f"  Tearsheet generation failed: {e}")

    try:
        saved = ctx.quantstats_save_plots(
            result,
            output_dir=str(ARTIFACTS_DIR),
        )
        for p in saved:
            print(f"  Plot saved: {p.name}")
    except Exception as e:
        print(f"  Plot generation failed: {e}")

    try:
        qs_metrics = ctx.quantstats(result)
        print(f"\n  QuantStats metrics:")
        for k, v in sorted(qs_metrics.metrics.items()):
            print(f"    {k:<20} {v:.4f}" if isinstance(v, float) else f"    {k:<20} {v}")
    except Exception as e:
        print(f"  Extended metrics failed: {e}")


def main():
    print("=" * 60)
    print("  VALIDATION: Baseline DCA 70/15/15")
    print("=" * 60)

    print("\nLoading data...")
    ctx = setup_context()
    print(f"Data range: {ctx._data_start} to {ctx._data_end}")

    RESULTS_DIR.mkdir(exist_ok=True)
    all_results = {}

    all_results["monte_carlo"] = validate_mc(ctx)
    all_results["oos"] = validate_oos(ctx)
    all_results["walk_forward"] = validate_walk_forward(ctx)
    all_results["events"] = validate_events(ctx)
    generate_tearsheet(ctx)

    output = RESULTS_DIR / "validation.json"
    output.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\n{'='*60}")
    print(f"All validation results saved to {output}")
    print(f"Tearsheet and plots saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
