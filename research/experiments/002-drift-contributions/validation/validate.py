"""Validation: MC, OOS holdout, walk-forward, event analysis, QuantStats.

Validates three DriftDCA candidate configurations against the baseline:
  - conservative: proportional, tilt=0.3, threshold=3.0
  - moderate:     proportional, tilt=1.0, threshold=3.0
  - aggressive:   stepped,      tilt=0.5, threshold=2.0

Builds BacktestSimulator directly (not via ResearchContext helpers) to
control pac_execution_days=[16] and the contribution distribution.
Follows the same structure as experiment 001's validate.py.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EXPERIMENT_DIR.parents[2] / "src"
BASELINE_STRATEGIES = EXPERIMENT_DIR.parents[0] / "001-baseline-dca" / "strategies"
DRIFT_STRATEGIES = EXPERIMENT_DIR / "strategies"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASELINE_STRATEGIES))
sys.path.insert(0, str(DRIFT_STRATEGIES))

from baseline_dca import BaselineDCA, BaselineDCAParams  # noqa: E402
from drift_dca import DriftDCAParams, DriftDCAStrategy  # noqa: E402

from pac.backtester.config import BacktestConfig  # noqa: E402
from pac.backtester.engine.simulator import BacktestSimulator, IterationResult  # noqa: E402
from pac.backtester.metrics.twrr import compute_mwrr, compute_twrr  # noqa: E402
from pac.backtester.research.context import ResearchContext  # noqa: E402
from pac.rules.discovery import discover_rules  # noqa: E402
from pac.rules.registry import SignalRegistry  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

START_DATE = date(2005, 1, 1)
END_DATE = date(2026, 4, 22)
CONTRIBUTION = {"min": Decimal("500"), "max": Decimal("700"), "distribution": "uniform"}
INITIAL_CASH = Decimal("0")

CANDIDATES: dict[str, dict | None] = {
    "baseline": None,
    "conservative": {
        "adjustment_formula": "proportional",
        "max_tilt_pct": 0.3,
        "threshold_pct": 3.0,
    },
    "moderate": {
        "adjustment_formula": "proportional",
        "max_tilt_pct": 1.0,
        "threshold_pct": 3.0,
    },
    "aggressive": {
        "adjustment_formula": "stepped",
        "max_tilt_pct": 0.5,
        "threshold_pct": 2.0,
    },
}

RESULTS_DIR = EXPERIMENT_DIR / "results"
ARTIFACTS_DIR = EXPERIMENT_DIR / "artifacts"

# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def setup_context() -> ResearchContext:
    """Load config, register both strategies, return ResearchContext."""
    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    ctx = ResearchContext.from_config(
        config_path,
        start_date=START_DATE,
        end_date=END_DATE,
        packs=["crisis"],
    )
    ctx.register_strategy("baseline_dca", BaselineDCA)
    ctx.register_strategy("drift_dca", DriftDCAStrategy)
    return ctx


def build_config(ctx: ResearchContext, **overrides) -> BacktestConfig:
    """Build a BacktestConfig with shared defaults.

    Args:
        ctx: Research context used for date bounds.
        **overrides: Any BacktestConfig field to override.

    Returns:
        BacktestConfig ready for BacktestSimulator.
    """
    defaults = {
        "strategy": "drift_dca",
        "strategy_params": {},
        "start_date": ctx.data_start,
        "end_date": ctx.data_end,
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
    """Discover all rules and return a populated SignalRegistry."""
    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)
    return registry


def _make_strategy(name: str, params: dict | None):
    """Instantiate the correct strategy for a given candidate name."""
    if name == "baseline":
        return BaselineDCA(BaselineDCAParams())
    return DriftDCAStrategy(DriftDCAParams(**params))


def run_single(
    ctx: ResearchContext,
    config: BacktestConfig,
    strategy_instance,
    seed: int = 42,
) -> IterationResult:
    """Run a single deterministic simulation iteration.

    Args:
        ctx: Research context with price data and settings.
        config: BacktestConfig for this run.
        strategy_instance: Instantiated strategy to use.
        seed: RNG seed for reproducibility.

    Returns:
        Single IterationResult.
    """
    signal_registry = build_signal_registry()
    simulator = BacktestSimulator(
        config=config,
        settings=ctx.settings,
        price_data=ctx.ticker_prices,
        signal_registry=signal_registry,
        strategy=strategy_instance,
        rng_seed=seed,
    )
    return simulator.run_iteration(0)


def run_mc(
    ctx: ResearchContext,
    strategy_instance,
    iterations: int = 50,
    seed: int = 42,
) -> list[IterationResult]:
    """Run N Monte Carlo iterations for a strategy.

    Resets the strategy between iterations to clear any per-run state.

    Args:
        ctx: Research context with price data and settings.
        strategy_instance: Instantiated strategy to simulate.
        iterations: Number of MC iterations to run.
        seed: Base RNG seed (each iteration offsets from this).

    Returns:
        List of IterationResult, one per iteration.
    """
    config = build_config(ctx, monte_carlo_iterations=iterations)
    signal_registry = build_signal_registry()
    simulator = BacktestSimulator(
        config=config,
        settings=ctx.settings,
        price_data=ctx.ticker_prices,
        signal_registry=signal_registry,
        strategy=strategy_instance,
        rng_seed=seed,
    )
    results = []
    for i in range(iterations):
        strategy_instance.reset()
        results.append(simulator.run_iteration(i))
    return results


# ---------------------------------------------------------------------------
# Validation phases
# ---------------------------------------------------------------------------


def _mc_stats(
    ctx: ResearchContext,
    candidate_name: str,
    params: dict | None,
    iterations: int = 50,
) -> dict:
    """Compute MC statistics for one candidate."""
    strategy = _make_strategy(candidate_name, params)
    mc_results = run_mc(ctx, strategy, iterations=iterations, seed=42)

    final_values = [float(r.final_value) for r in mc_results]
    p5, median, p95 = np.percentile(final_values, [5, 50, 95])

    all_metrics: dict[str, list[float]] = {}
    for r in mc_results:
        m = ctx.compute_metrics(r, ["sharpe", "cagr", "max_drawdown", "sortino", "calmar"])
        for k, v in m.items():
            all_metrics.setdefault(k, []).append(v)

    metric_bands: dict[str, dict] = {}
    for k, vals in all_metrics.items():
        arr = np.array(vals)
        mp5, mmed, mp95 = np.nanpercentile(arr, [5, 50, 95])
        metric_bands[k] = {
            "p5": round(float(mp5), 4),
            "median": round(float(mmed), 4),
            "p95": round(float(mp95), 4),
        }

    twrr_vals = [compute_twrr(r) for r in mc_results]
    mwrr_vals = [compute_mwrr(r, initial_cash=INITIAL_CASH) for r in mc_results]
    twrr_arr = np.array(twrr_vals)
    mwrr_arr = np.array(mwrr_vals)
    metric_bands["twrr"] = {
        "p5": round(float(np.nanpercentile(twrr_arr, 5)), 4),
        "median": round(float(np.nanpercentile(twrr_arr, 50)), 4),
        "p95": round(float(np.nanpercentile(twrr_arr, 95)), 4),
    }
    metric_bands["mwrr"] = {
        "p5": round(float(np.nanpercentile(mwrr_arr, 5)), 4),
        "median": round(float(np.nanpercentile(mwrr_arr, 50)), 4),
        "p95": round(float(np.nanpercentile(mwrr_arr, 95)), 4),
    }

    return {
        "iterations": iterations,
        "final_value": {
            "p5": round(p5, 2),
            "median": round(median, 2),
            "p95": round(p95, 2),
        },
        "metrics": metric_bands,
    }


def validate_mc(ctx: ResearchContext) -> dict:
    """Monte Carlo simulation (N=50) for all four variants."""
    print("\n[1/5] Monte Carlo simulation (N=50, contribution variation)...")

    all_stats: dict[str, dict] = {}
    for name, params in CANDIDATES.items():
        print(f"  Running {name}...")
        all_stats[name] = _mc_stats(ctx, name, params, iterations=50)

    # Print comparison table: rows=metrics, cols=candidates
    metric_keys = ["twrr", "mwrr", "sharpe", "cagr", "max_drawdown", "sortino", "calmar"]
    col_w = 22
    header = f"  {'Metric':<15}" + "".join(f"{n:>{col_w}}" for n in CANDIDATES)
    print()
    print(header)
    print("  " + "-" * (len(header) - 2))

    def _band_str(band: dict) -> str:
        return f"{band['median']:.4f} [{band['p5']:.4f}, {band['p95']:.4f}]"

    for key in metric_keys:
        row = f"  {key:<15}"
        for name in CANDIDATES:
            band = all_stats[name]["metrics"].get(key, {})
            cell = _band_str(band) if band else "n/a"
            row += f"{cell:>{col_w}}"
        print(row)

    fv_row = f"  {'final_value':<15}"
    for name in CANDIDATES:
        fv = all_stats[name]["final_value"]
        cell = f"{fv['median']:,.0f}"
        fv_row += f"{cell:>{col_w}}"
    print(fv_row)

    return all_stats


def _oos_stats(
    ctx: ResearchContext,
    candidate_name: str,
    params: dict | None,
    split_date: date,
) -> dict:
    """OOS stats for one candidate (70/30 split)."""
    strategy_is = _make_strategy(candidate_name, params)
    strategy_oos = _make_strategy(candidate_name, params)

    is_config = build_config(
        ctx,
        start_date=ctx.data_start,
        end_date=split_date - timedelta(days=1),
    )
    oos_config = build_config(ctx, start_date=split_date, end_date=ctx.data_end)

    is_result = run_single(ctx, is_config, strategy_is)
    oos_result = run_single(ctx, oos_config, strategy_oos)

    is_m = ctx.compute_metrics(is_result, ["sharpe", "cagr", "max_drawdown"])
    oos_m = ctx.compute_metrics(oos_result, ["sharpe", "cagr", "max_drawdown"])
    is_twrr = compute_twrr(is_result)
    oos_twrr = compute_twrr(oos_result)

    deg = (
        oos_m["sharpe"] / is_m["sharpe"]
        if is_m.get("sharpe") and is_m["sharpe"] != 0
        else float("nan")
    )

    return {
        "in_sample": {
            "metrics": {k: round(v, 4) for k, v in is_m.items()},
            "twrr": round(is_twrr, 4),
            "final_value": float(is_result.final_value),
        },
        "out_of_sample": {
            "metrics": {k: round(v, 4) for k, v in oos_m.items()},
            "twrr": round(oos_twrr, 4),
            "final_value": float(oos_result.final_value),
        },
        "degradation_ratio": round(deg, 4),
    }


def validate_oos(ctx: ResearchContext) -> dict:
    """Out-of-sample holdout validation (70/30 split) for all variants."""
    print("\n[2/5] Out-of-sample validation (70/30 split)...")
    total_days = (ctx.data_end - ctx.data_start).days
    split_date = ctx.data_start + timedelta(days=int(total_days * 0.7))
    print(f"  Split date: {split_date}")

    all_stats: dict[str, dict] = {}
    for name, params in CANDIDATES.items():
        print(f"  Running {name}...")
        all_stats[name] = _oos_stats(ctx, name, params, split_date)
        all_stats[name]["split_date"] = str(split_date)

    # Print comparison
    print()
    col_w = 15
    header = f"  {'Metric':<20}" + "".join(f"{n:>{col_w}}" for n in CANDIDATES)
    print(header)
    print("  " + "-" * (len(header) - 2))

    for phase_key, phase_label in [("in_sample", "IS"), ("out_of_sample", "OOS")]:
        for metric in ["sharpe", "cagr", "max_drawdown", "twrr"]:
            row_label = f"{phase_label} {metric}"
            row = f"  {row_label:<20}"
            for name in CANDIDATES:
                if metric == "twrr":
                    val = all_stats[name][phase_key]["twrr"]
                else:
                    val = all_stats[name][phase_key]["metrics"].get(metric, float("nan"))
                row += f"{val:>{col_w}.4f}"
            print(row)

    deg_row = f"  {'degradation_ratio':<20}"
    for name in CANDIDATES:
        val = all_stats[name]["degradation_ratio"]
        deg_row += f"{val:>{col_w}.4f}"
    print(deg_row)

    return all_stats


def _wf_stats(
    ctx: ResearchContext,
    candidate_name: str,
    params: dict | None,
    windows: list[tuple[date, date, date, date]],
) -> dict:
    """Walk-forward stats for one candidate."""
    wf_results = []
    oos_sharpes = []
    for is_start, is_end_dt, oos_start, oos_end in windows:
        strategy_is = _make_strategy(candidate_name, params)
        strategy_oos = _make_strategy(candidate_name, params)

        is_config = build_config(ctx, start_date=is_start, end_date=is_end_dt)
        oos_config = build_config(ctx, start_date=oos_start, end_date=oos_end)

        is_result = run_single(ctx, is_config, strategy_is)
        oos_result = run_single(ctx, oos_config, strategy_oos)

        is_m = ctx.compute_metrics(is_result, ["sharpe", "cagr", "max_drawdown"])
        oos_m = ctx.compute_metrics(oos_result, ["sharpe", "cagr", "max_drawdown"])
        oos_sharpes.append(oos_m["sharpe"])

        wf_results.append({
            "is_period": f"{is_start} to {is_end_dt}",
            "oos_period": f"{oos_start} to {oos_end}",
            "is_metrics": {k: round(v, 4) for k, v in is_m.items()},
            "oos_metrics": {k: round(v, 4) for k, v in oos_m.items()},
        })

    stability = (
        statistics.mean(oos_sharpes) / statistics.stdev(oos_sharpes)
        if len(oos_sharpes) > 1 and statistics.stdev(oos_sharpes) > 0
        else float("nan")
    )
    return {"windows": wf_results, "stability_score": round(stability, 4)}


def validate_walk_forward(ctx: ResearchContext) -> dict:
    """Walk-forward validation (10yr IS, 5yr step) for all variants."""
    print("\n[3/5] Walk-forward validation (10yr IS, 5yr step)...")

    # Build window schedule once; reuse across candidates.
    windows: list[tuple[date, date, date, date]] = []
    is_end = ctx.data_start + timedelta(days=10 * 365)
    step = timedelta(days=5 * 365)
    while is_end < ctx.data_end:
        oos_end = min(is_end + step, ctx.data_end)
        if (oos_end - is_end).days < 90:
            break
        windows.append((ctx.data_start, is_end, is_end + timedelta(days=1), oos_end))
        is_end = oos_end

    print(f"  {len(windows)} windows defined.")

    all_stats: dict[str, dict] = {}
    for name, params in CANDIDATES.items():
        print(f"  Running {name}...")
        all_stats[name] = _wf_stats(ctx, name, params, windows)

    # Print per-window OOS sharpe comparison
    print()
    col_w = 14
    header = f"  {'Window':<8}" + "".join(f"{n:>{col_w}}" for n in CANDIDATES)
    print(header)
    print("  " + "-" * (len(header) - 2))

    n_windows = len(windows)
    for i in range(n_windows):
        row = f"  {'W' + str(i + 1):<8}"
        for name in CANDIDATES:
            oos_m = all_stats[name]["windows"][i]["oos_metrics"]
            row += f"{oos_m['sharpe']:>{col_w}.4f}"
        print(row)

    stab_row = f"  {'stability':<8}"
    for name in CANDIDATES:
        stab_row += f"{all_stats[name]['stability_score']:>{col_w}.4f}"
    print(stab_row)

    return all_stats


def _event_stats(
    ctx: ResearchContext,
    candidate_name: str,
    params: dict | None,
) -> dict:
    """Event analysis for one candidate over the full period."""
    strategy = _make_strategy(candidate_name, params)
    config = build_config(ctx)
    result = run_single(ctx, config, strategy)

    crises = ctx.calendars["crises"]
    relevant = [
        e
        for e in crises.events
        if e.start <= ctx.data_end and e.end >= ctx.data_start
    ]

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

    return {"events": per_event}


def validate_events(ctx: ResearchContext) -> dict:
    """Event analysis against crisis calendar for all variants."""
    print("\n[4/5] Event analysis (crisis calendar)...")

    all_stats: dict[str, dict] = {}
    for name, params in CANDIDATES.items():
        print(f"  Running {name}...")
        all_stats[name] = _event_stats(ctx, name, params)

    # Print comparison table: rows=events, cols=candidates
    events_by_name: dict[str, dict[str, float]] = {}
    for name in CANDIDATES:
        for ev in all_stats[name]["events"]:
            events_by_name.setdefault(ev["name"], {})[name] = ev["return"]

    col_w = 14
    print()
    header = f"  {'Event':<35}" + "".join(f"{n:>{col_w}}" for n in CANDIDATES)
    print(header)
    print("  " + "-" * (len(header) - 2))

    for event_name, returns in sorted(events_by_name.items()):
        row = f"  {event_name:<35}"
        for cname in CANDIDATES:
            ret = returns.get(cname, float("nan"))
            if ret != ret:
                row += f"{'n/a':>{col_w}}"
            else:
                row += f"{ret:>+{col_w}.4f}"
        print(row)

    return all_stats


def generate_tearsheet(ctx: ResearchContext, best_candidate: str) -> None:
    """Generate QuantStats HTML tearsheet for the best candidate.

    Args:
        ctx: Research context.
        best_candidate: Name of the candidate to generate the tearsheet for.
    """
    print(f"\n[5/5] Generating QuantStats tearsheet for '{best_candidate}'...")
    ARTIFACTS_DIR.mkdir(exist_ok=True)

    params = CANDIDATES[best_candidate]
    strategy = _make_strategy(best_candidate, params)
    config = build_config(ctx)
    result = run_single(ctx, config, strategy)

    try:
        report_path = ctx.quantstats_report(
            result,
            output=str(ARTIFACTS_DIR / f"tearsheet_{best_candidate}.html"),
            title=f"DriftDCA — {best_candidate}",
        )
        print(f"  Tearsheet saved to {report_path}")
    except Exception as e:
        print(f"  Tearsheet generation failed (quantstats may not be available): {e}")

    try:
        saved = ctx.quantstats_save_plots(result, output_dir=str(ARTIFACTS_DIR))
        for p in saved:
            print(f"  Plot saved: {p.name}")
    except Exception as e:
        print(f"  Plot generation failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point: run all validation phases and save results."""
    print("=" * 65)
    print("  VALIDATION: DriftDCA — conservative / moderate / aggressive")
    print("=" * 65)

    print("\nLoading data...")
    ctx = setup_context()
    print(f"Data range: {ctx.data_start} to {ctx.data_end}")

    RESULTS_DIR.mkdir(exist_ok=True)
    all_results: dict[str, dict] = {}

    all_results["monte_carlo"] = validate_mc(ctx)
    all_results["oos"] = validate_oos(ctx)
    all_results["walk_forward"] = validate_walk_forward(ctx)
    all_results["events"] = validate_events(ctx)

    # Best candidate heuristic: highest median MC Sharpe among non-baseline.
    best = max(
        [n for n in CANDIDATES if n != "baseline"],
        key=lambda n: (
            all_results["monte_carlo"][n]["metrics"].get("sharpe", {}).get("median", 0.0)
        ),
    )
    generate_tearsheet(ctx, best)

    output = RESULTS_DIR / "validation.json"
    output.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\n{'='*65}")
    print(f"All validation results saved to {output}")
    print(f"Tearsheet saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
