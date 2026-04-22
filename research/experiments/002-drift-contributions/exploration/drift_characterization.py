"""Drift characterization: magnitude, persistence, and regime behavior.

Phase 1 (Exploration) — Script 1 of 4.

Runs the baseline DCA simulation (N=1, deterministic) and analyzes the
drift of each asset's actual allocation vs its 70/15/15 target. Answers:
  - How large does drift get in practice?
  - How long does it persist before mean-reverting?
  - Is there enough room for contribution steering to matter?

Kill criterion: if max |drift| < 2pp across all assets, contribution
steering has negligible room and the hypothesis is rejected.

Results saved to: results/drift_characterization.json
Plots saved to:   artifacts/drift_over_time.png
                  artifacts/drift_distributions.png
                  artifacts/drift_autocorrelation.png
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EXPERIMENT_DIR.parents[2] / "src"
BASELINE_STRATEGIES = EXPERIMENT_DIR.parents[0] / "001-baseline-dca" / "strategies"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASELINE_STRATEGIES))

import numpy as np
import pandas as pd
from baseline_dca import BaselineDCA, BaselineDCAParams  # noqa: E402

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import BacktestSimulator, IterationResult
from pac.backtester.research.context import ResearchContext
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry


def build_signal_registry(ctx: ResearchContext) -> SignalRegistry:
    """Build a SignalRegistry from the context's settings."""
    rule_classes = discover_rules()
    registry = SignalRegistry()
    for sig_cfg in ctx.settings.signals:
        if sig_cfg.rule in rule_classes:
            rule_cls = rule_classes[sig_cfg.rule]
            registry.register(rule_cls)
    return registry


def run_baseline_simulation(ctx: ResearchContext) -> IterationResult:
    """Run deterministic N=1 baseline simulation."""
    config = BacktestConfig(
        strategy="baseline_dca",
        strategy_params={},
        start_date=ctx.data_start,
        end_date=ctx.data_end,
        initial_cash=Decimal("0"),
        monthly_contribution={"min": Decimal("500"), "max": Decimal("700"), "distribution": "uniform"},
        pac_execution_days=[16],
        settlement_fee=Decimal("1.00"),
        spread_bps=Decimal("10"),
        slippage_days=(0, 0),
        monte_carlo_iterations=1,
        tax_regime="italian",
    )
    strategy = BaselineDCA(BaselineDCAParams())
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


def build_drift_dataframe(result: IterationResult, targets: dict[str, Decimal]) -> pd.DataFrame:
    """Build a DataFrame of per-asset drift (actual_pct - target_pct) over time.

    Skips early days where total_value == 0 (before first contribution).

    Args:
        result: Single iteration result.
        targets: Asset ID to target allocation (as Decimal percentage, e.g. 70.0).

    Returns:
        DataFrame with date index and one column per asset, values in percentage points.
    """
    rows: list[dict[str, object]] = []
    for dv in result.daily_values:
        if dv.total_value == 0:
            continue
        row: dict[str, object] = {"date": dv.date}
        for asset_id, target in targets.items():
            actual = dv.allocations.get(asset_id, Decimal("0"))
            row[asset_id] = float(actual) - float(target)
        rows.append(row)
    df = pd.DataFrame(rows).set_index("date")
    df.index = pd.to_datetime(df.index)
    return df


def analyze_drift_distribution(drift_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Compute distributional statistics for each asset's drift series.

    Args:
        drift_df: DataFrame with date index and one column per asset (drift in pp).

    Returns:
        Dict mapping asset_id to a stats dict with keys:
        mean, std, min, p5, p25, p50, p75, p95, max,
        pct_above_2pp, pct_above_5pp, pct_above_10pp.
    """
    stats: dict[str, dict[str, float]] = {}
    for col in drift_df.columns:
        s = drift_df[col]
        abs_s = s.abs()
        stats[str(col)] = {
            "mean": float(s.mean()),
            "std": float(s.std()),
            "min": float(s.min()),
            "p5": float(s.quantile(0.05)),
            "p25": float(s.quantile(0.25)),
            "p50": float(s.quantile(0.50)),
            "p75": float(s.quantile(0.75)),
            "p95": float(s.quantile(0.95)),
            "max": float(s.max()),
            "abs_mean": float(abs_s.mean()),
            "abs_max": float(abs_s.max()),
            "pct_above_2pp": float((abs_s > 2.0).mean() * 100),
            "pct_above_5pp": float((abs_s > 5.0).mean() * 100),
            "pct_above_10pp": float((abs_s > 10.0).mean() * 100),
        }
    return stats


def analyze_drift_persistence(drift_df: pd.DataFrame, max_lag: int = 60) -> dict[str, list[float]]:
    """Compute autocorrelation at lags 1..max_lag for each asset's drift.

    Args:
        drift_df: DataFrame with date index and one column per asset.
        max_lag: Maximum lag (trading days) to compute ACF for.

    Returns:
        Dict mapping asset_id to list of ACF values at lags 1..max_lag.
    """
    acf: dict[str, list[float]] = {}
    for col in drift_df.columns:
        s = drift_df[col].dropna()
        lags = range(1, max_lag + 1)
        acf[str(col)] = [float(s.autocorr(lag=lag)) for lag in lags]
    return acf


def estimate_half_life(acf_values: list[float]) -> float:
    """Estimate persistence half-life from ACF values.

    Finds the first lag where ACF drops below 0.5 (interpolated).

    Args:
        acf_values: List of ACF values at lags 1, 2, ..., N.

    Returns:
        Half-life in trading days, or inf if ACF stays above 0.5.
    """
    for i, val in enumerate(acf_values):
        if val <= 0.5:
            if i == 0:
                return 1.0
            # linear interpolation between lag i and i+1
            prev_val = acf_values[i - 1]
            frac = (prev_val - 0.5) / (prev_val - val)
            return float(i + frac)
    return float("inf")


def save_plots(drift_df: pd.DataFrame, acf_data: dict[str, list[float]]) -> None:
    """Save drift analysis plots to artifacts/."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("matplotlib not available — skipping plots")
        return

    artifacts_dir = EXPERIMENT_DIR / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    assets = list(drift_df.columns)
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    # Plot 1: drift over time
    fig, axes = plt.subplots(len(assets), 1, figsize=(14, 3 * len(assets)), sharex=True)
    if len(assets) == 1:
        axes = [axes]
    for ax, asset, color in zip(axes, assets, colors):
        ax.plot(drift_df.index, drift_df[asset], linewidth=0.8, color=color, alpha=0.9)
        ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
        ax.axhline(5, color="red", linewidth=0.5, linestyle=":", alpha=0.6)
        ax.axhline(-5, color="red", linewidth=0.5, linestyle=":", alpha=0.6)
        ax.set_ylabel(f"{asset}\ndrift (pp)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Date")
    fig.suptitle("Portfolio Drift: Actual Allocation - Target (70/15/15)", fontsize=12)
    plt.tight_layout()
    plt.savefig(artifacts_dir / "drift_over_time.png", dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {artifacts_dir / 'drift_over_time.png'}")

    # Plot 2: drift distributions (histogram per asset)
    fig, axes = plt.subplots(1, len(assets), figsize=(5 * len(assets), 4))
    if len(assets) == 1:
        axes = [axes]
    for ax, asset, color in zip(axes, assets, colors):
        data = drift_df[asset].dropna()
        ax.hist(data, bins=50, color=color, alpha=0.7, edgecolor="none")
        ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_title(f"{asset}")
        ax.set_xlabel("Drift (pp)")
        ax.set_ylabel("Days")
        ax.grid(True, alpha=0.3)
    fig.suptitle("Drift Distribution per Asset", fontsize=12)
    plt.tight_layout()
    plt.savefig(artifacts_dir / "drift_distributions.png", dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {artifacts_dir / 'drift_distributions.png'}")

    # Plot 3: autocorrelation decay
    fig, ax = plt.subplots(figsize=(10, 4))
    lags = list(range(1, len(next(iter(acf_data.values()))) + 1))
    for asset, color in zip(assets, colors):
        ax.plot(lags, acf_data[asset], label=asset, color=color, linewidth=1.5)
    ax.axhline(0.5, color="gray", linewidth=0.8, linestyle="--", label="ACF=0.5")
    ax.axhline(0.0, color="black", linewidth=0.6)
    ax.set_xlabel("Lag (trading days)")
    ax.set_ylabel("Autocorrelation")
    ax.set_title("Drift Autocorrelation Decay (Persistence)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(artifacts_dir / "drift_autocorrelation.png", dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {artifacts_dir / 'drift_autocorrelation.png'}")


def print_summary(
    dist_stats: dict[str, dict[str, float]],
    acf_data: dict[str, list[float]],
    targets: dict[str, Decimal],
) -> None:
    """Print human-readable summary to stdout."""
    print("\n" + "=" * 60)
    print("  DRIFT CHARACTERIZATION RESULTS")
    print("=" * 60)

    # Kill criterion check
    max_abs_drift = max(s["abs_max"] for s in dist_stats.values())
    print(f"\n  Kill criterion: max |drift| > 2pp?")
    print(f"  Max absolute drift observed: {max_abs_drift:.2f}pp")
    if max_abs_drift < 2.0:
        print("  *** KILL: drift too small — contribution steering has no room ***")
    else:
        print("  PASS: sufficient drift range for contribution steering")

    print(f"\n  {'Asset':<10} {'Target':>8} {'Mean':>8} {'AbsMean':>8} "
          f"{'AbsMax':>8} {'>2pp%':>7} {'>5pp%':>7} {'>10pp%':>7}")
    print("  " + "-" * 70)
    for asset_id, stats in dist_stats.items():
        target_pct = float(targets.get(asset_id, Decimal("0")))
        print(f"  {asset_id:<10} {target_pct:>7.1f}% {stats['mean']:>+8.2f} "
              f"{stats['abs_mean']:>8.2f} {stats['abs_max']:>8.2f} "
              f"{stats['pct_above_2pp']:>7.1f} {stats['pct_above_5pp']:>7.1f} "
              f"{stats['pct_above_10pp']:>7.1f}")

    print(f"\n  {'Asset':<10} {'HalfLife (days)':>16}")
    print("  " + "-" * 28)
    for asset_id, acf_vals in acf_data.items():
        hl = estimate_half_life(acf_vals)
        hl_str = f"{hl:.1f}" if hl != float("inf") else "inf"
        print(f"  {asset_id:<10} {hl_str:>16}")


def main() -> None:
    """Entry point for drift characterization exploration."""
    config_path = EXPERIMENT_DIR / "configs" / "baseline.yaml"
    print(f"Loading config: {config_path}")
    print("Fetching price data with proxy chains (may take a moment)...")

    ctx = ResearchContext.from_config(
        config_path,
        start_date=date(2005, 1, 1),
        end_date=date(2026, 4, 22),
        packs=["crisis"],
    )
    ctx.register_strategy("baseline_dca", BaselineDCA)

    print(f"Data range: {ctx.data_start} to {ctx.data_end}")
    for asset_id, series in ctx.prices.items():
        print(f"  {asset_id}: {series.start_date} to {series.end_date} ({len(series.bars)} bars)")

    print("\nRunning baseline simulation (N=1, deterministic)...")
    result = run_baseline_simulation(ctx)
    print(f"  Simulation complete: {len(result.daily_values)} daily snapshots, "
          f"{len(result.trades)} trades")

    targets = ctx.settings.target_allocations
    drift_df = build_drift_dataframe(result, targets)
    print(f"  Drift DataFrame: {len(drift_df)} rows (after stripping leading zeros)")

    print("\nAnalyzing drift distribution...")
    dist_stats = analyze_drift_distribution(drift_df)

    print("Analyzing drift persistence (ACF up to lag 60)...")
    acf_data = analyze_drift_persistence(drift_df, max_lag=60)

    half_lives = {
        asset_id: estimate_half_life(acf_vals)
        for asset_id, acf_vals in acf_data.items()
    }

    print_summary(dist_stats, acf_data, targets)

    print("\nSaving plots...")
    save_plots(drift_df, acf_data)

    # Save structured results
    results_dir = EXPERIMENT_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    output = results_dir / "drift_characterization.json"
    summary = {
        "period": f"{ctx.data_start} to {ctx.data_end}",
        "trading_days_with_data": len(drift_df),
        "targets": {k: float(v) for k, v in targets.items()},
        "distribution_stats": dist_stats,
        "autocorrelation_lags": list(range(1, 61)),
        "autocorrelation": {k: [round(v, 4) for v in vals] for k, vals in acf_data.items()},
        "half_life_days": {k: (v if v != float("inf") else None) for k, v in half_lives.items()},
    }
    output.write_text(json.dumps(summary, indent=2))
    print(f"\nResults saved to {output}")


if __name__ == "__main__":
    main()
