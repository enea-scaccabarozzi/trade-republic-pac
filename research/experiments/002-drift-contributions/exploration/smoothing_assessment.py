"""Smoothing assessment: spot vs SMA vs EMA for drift signals.

Phase 1 (Exploration) — Script 2 of 4.

The contribution-steering strategy will need to act on drift observations.
Raw (spot) drift is noisy — a single bad day could trigger unnecessary
reallocation. This script quantifies the tradeoff between:
  - Noise reduction: how much variance smoothing removes
  - Lag: how many days behind the smoothed signal is

Purpose: determine whether to use spot drift, SMA, or EMA in the
strategy, and which window sizes are worth investigating.

Narrow criterion: if smoothing adds >5 days of lag but reduces variance
by <20%, the gain is too small relative to the cost — use spot drift.

Results saved to: results/smoothing_assessment.json
Plots saved to:   artifacts/smoothing_overlay_<asset>.png
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


WINDOWS = [5, 10, 20, 40]


def build_signal_registry(ctx: ResearchContext) -> SignalRegistry:
    """Build a SignalRegistry from context settings."""
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


def build_drift_series(result: IterationResult, targets: dict[str, Decimal]) -> pd.DataFrame:
    """Build spot drift DataFrame (actual_pct - target_pct) for each asset.

    Skips early rows where total_value == 0.
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


def compute_smoothed_variants(
    spot: pd.Series,
    windows: list[int],
) -> dict[str, pd.Series]:
    """Compute SMA and EMA variants for each window size.

    Args:
        spot: Spot drift series.
        windows: List of window / span sizes to test.

    Returns:
        Dict mapping variant label to smoothed Series.
        Keys follow the pattern "sma_N" and "ema_N".
    """
    variants: dict[str, pd.Series] = {"spot": spot}
    for w in windows:
        variants[f"sma_{w}"] = spot.rolling(window=w, min_periods=1).mean()
        variants[f"ema_{w}"] = spot.ewm(span=w, adjust=False).mean()
    return variants


def variance_ratio(spot: pd.Series, smoothed: pd.Series) -> float:
    """Compute variance ratio: var(smoothed) / var(spot).

    Ratio < 1 means noise reduction; 0 means completely smooth.
    """
    var_spot = float(spot.var())
    if var_spot == 0:
        return 1.0
    return float(smoothed.var()) / var_spot


def cross_correlation_lag(spot: pd.Series, smoothed: pd.Series, max_lag: int = 30) -> int:
    """Find the lag at which smoothed series best correlates with spot.

    A lag of k means smoothed[t] ~ spot[t - k], i.e., k days behind spot.

    Args:
        spot: Original spot drift series.
        smoothed: Smoothed drift series.
        max_lag: Maximum lag in trading days to search.

    Returns:
        Lag (>=0) in trading days where cross-correlation peaks.
    """
    best_lag = 0
    best_corr = -float("inf")
    for lag in range(0, max_lag + 1):
        if lag == 0:
            corr = float(spot.corr(smoothed))
        else:
            corr = float(spot.iloc[lag:].corr(smoothed.iloc[:-lag]))
        if corr > best_corr:
            best_corr = corr
            best_lag = lag
    return best_lag


def analyze_smoothing(
    drift_df: pd.DataFrame,
    windows: list[int],
) -> dict[str, dict[str, dict[str, float]]]:
    """Analyze smoothing tradeoffs per asset.

    Returns nested dict: asset_id -> variant_label -> {variance_ratio, lag_days}.
    """
    results: dict[str, dict[str, dict[str, float]]] = {}
    for col in drift_df.columns:
        spot = drift_df[col].dropna()
        variants = compute_smoothed_variants(spot, windows)
        asset_results: dict[str, dict[str, float]] = {}
        for label, series in variants.items():
            if label == "spot":
                asset_results[label] = {"variance_ratio": 1.0, "lag_days": 0.0}
                continue
            vr = variance_ratio(spot, series)
            lag = cross_correlation_lag(spot, series)
            asset_results[label] = {
                "variance_ratio": round(vr, 4),
                "lag_days": float(lag),
                "noise_reduction_pct": round((1.0 - vr) * 100, 2),
            }
        results[str(col)] = asset_results
    return results


def save_plots(
    drift_df: pd.DataFrame,
    windows: list[int],
) -> None:
    """Save overlay plots comparing spot vs smoothed variants per asset."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("matplotlib not available — skipping plots")
        return

    artifacts_dir = EXPERIMENT_DIR / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    for col in drift_df.columns:
        spot = drift_df[col]
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # Top: SMA variants
        axes[0].plot(spot.index, spot, color="gray", linewidth=0.5, alpha=0.6, label="spot")
        colors_sma = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
        for w, c in zip(windows, colors_sma):
            sma = spot.rolling(window=w, min_periods=1).mean()
            axes[0].plot(spot.index, sma, linewidth=1.2, color=c, label=f"SMA({w})")
        axes[0].axhline(0, color="black", linewidth=0.5, linestyle="--")
        axes[0].set_ylabel("Drift (pp)")
        axes[0].set_title(f"{col} — SMA Smoothing")
        axes[0].legend(loc="upper right", fontsize=8)
        axes[0].grid(True, alpha=0.3)

        # Bottom: EMA variants
        axes[1].plot(spot.index, spot, color="gray", linewidth=0.5, alpha=0.6, label="spot")
        colors_ema = ["#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
        for w, c in zip(windows, colors_ema):
            ema = spot.ewm(span=w, adjust=False).mean()
            axes[1].plot(spot.index, ema, linewidth=1.2, color=c, label=f"EMA({w})")
        axes[1].axhline(0, color="black", linewidth=0.5, linestyle="--")
        axes[1].set_ylabel("Drift (pp)")
        axes[1].set_xlabel("Date")
        axes[1].set_title(f"{col} — EMA Smoothing")
        axes[1].legend(loc="upper right", fontsize=8)
        axes[1].grid(True, alpha=0.3)
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        plt.tight_layout()
        fname = artifacts_dir / f"smoothing_overlay_{col}.png"
        plt.savefig(fname, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"  Saved: {fname}")


def print_summary(
    analysis: dict[str, dict[str, dict[str, float]]],
    windows: list[int],
) -> None:
    """Print tradeoff table: noise reduction vs lag per variant per asset."""
    print("\n" + "=" * 70)
    print("  SMOOTHING ASSESSMENT RESULTS")
    print("=" * 70)
    print(f"\n  Narrow criterion: lag >5d AND noise reduction <20% → use spot drift")

    for asset_id, variants in analysis.items():
        print(f"\n  {asset_id}:")
        print(f"  {'Variant':<12} {'Var Ratio':>10} {'Noise Reduc%':>14} {'Lag (days)':>12}")
        print("  " + "-" * 50)
        for label, metrics in variants.items():
            vr = metrics["variance_ratio"]
            nr = metrics.get("noise_reduction_pct", 0.0)
            lag = metrics["lag_days"]
            flag = ""
            if label != "spot" and lag > 5 and nr < 20:
                flag = "  ← NARROW CRITERION: skip"
            print(f"  {label:<12} {vr:>10.4f} {nr:>14.2f} {lag:>12.0f}{flag}")


def main() -> None:
    """Entry point for smoothing assessment exploration."""
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
    print("\nRunning baseline simulation (N=1, deterministic)...")
    result = run_baseline_simulation(ctx)
    print(f"  {len(result.daily_values)} daily snapshots")

    targets = ctx.settings.target_allocations
    drift_df = build_drift_series(result, targets)
    print(f"  Drift DataFrame: {len(drift_df)} rows")

    print(f"\nAnalyzing smoothing for windows: {WINDOWS}...")
    analysis = analyze_smoothing(drift_df, WINDOWS)

    print_summary(analysis, WINDOWS)

    print("\nSaving overlay plots...")
    save_plots(drift_df, WINDOWS)

    results_dir = EXPERIMENT_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    output = results_dir / "smoothing_assessment.json"
    output.write_text(json.dumps({
        "windows": WINDOWS,
        "analysis": analysis,
    }, indent=2))
    print(f"\nResults saved to {output}")


if __name__ == "__main__":
    main()
