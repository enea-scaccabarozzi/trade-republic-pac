"""Contribution capacity: how much drift can contributions correct over time?

Phase 1 (Exploration) — Script 3 of 4.

As the portfolio grows, monthly contributions become a smaller fraction
of total portfolio value. This limits how much drift each contribution
can correct. This script quantifies:
  - Contribution-to-portfolio ratio over the 21-year simulation
  - Maximum drift correction achievable per monthly contribution
  - Whether the strategy's value is front-loaded (early years only)
  - Crossover point where contributions become negligibly small

Key question: when does the contribution-to-portfolio ratio drop below
1% (meaning a full month's contribution can correct at most 1pp of drift)?

Results saved to: results/contribution_capacity.json
Plots saved to:   artifacts/contribution_capacity.png
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

MEAN_CONTRIBUTION_EUR = 600.0  # midpoint of U(500, 700)


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


def build_capacity_dataframe(
    result: IterationResult,
    mean_contribution_eur: float = MEAN_CONTRIBUTION_EUR,
) -> pd.DataFrame:
    """Build a DataFrame of portfolio value and contribution capacity over time.

    For each trading day:
      - total_value: portfolio value in EUR
      - contribution_ratio: mean_contribution / total_value (if total_value > 0)
      - max_drift_correction_pp: contribution_ratio * 100 (max pp of drift correctable)

    Args:
        result: Single iteration result.
        mean_contribution_eur: Expected monthly contribution in EUR.

    Returns:
        DataFrame with date index and columns:
        [total_value, contribution_ratio, max_drift_correction_pp].
    """
    rows: list[dict[str, object]] = []
    for dv in result.daily_values:
        tv = float(dv.total_value)
        if tv <= 0:
            continue
        ratio = mean_contribution_eur / tv
        rows.append({
            "date": dv.date,
            "total_value": tv,
            "contribution_ratio": ratio,
            "max_drift_correction_pp": ratio * 100.0,
        })
    df = pd.DataFrame(rows).set_index("date")
    df.index = pd.to_datetime(df.index)
    return df


def find_crossover_dates(
    capacity_df: pd.DataFrame,
    thresholds_pct: list[float],
) -> dict[str, str | None]:
    """Find when max_drift_correction_pp first drops below each threshold.

    Args:
        capacity_df: Output of build_capacity_dataframe().
        thresholds_pct: Thresholds in percentage points (e.g. [5.0, 2.0, 1.0, 0.5]).

    Returns:
        Dict mapping threshold string to ISO date string (or None if never crossed).
    """
    crossovers: dict[str, str | None] = {}
    for t in thresholds_pct:
        mask = capacity_df["max_drift_correction_pp"] < t
        if mask.any():
            first_date = capacity_df.index[mask][0]
            crossovers[f"below_{t}pp"] = str(first_date.date())
        else:
            crossovers[f"below_{t}pp"] = None
    return crossovers


def analyze_by_year(capacity_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Summarize mean contribution capacity per calendar year.

    Args:
        capacity_df: Output of build_capacity_dataframe().

    Returns:
        Dict mapping year string to dict with mean_ratio and mean_max_correction_pp.
    """
    by_year: dict[str, dict[str, float]] = {}
    for year, group in capacity_df.groupby(capacity_df.index.year):
        by_year[str(year)] = {
            "mean_contribution_ratio": float(group["contribution_ratio"].mean()),
            "mean_max_drift_correction_pp": float(group["max_drift_correction_pp"].mean()),
            "portfolio_value_start": float(group["total_value"].iloc[0]),
            "portfolio_value_end": float(group["total_value"].iloc[-1]),
        }
    return by_year


def save_plots(capacity_df: pd.DataFrame) -> None:
    """Save portfolio growth and contribution capacity plots."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("matplotlib not available — skipping plots")
        return

    artifacts_dir = EXPERIMENT_DIR / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Top: portfolio value
    ax1.fill_between(
        capacity_df.index,
        capacity_df["total_value"] / 1000,
        alpha=0.4,
        color="#1f77b4",
        label="Portfolio value",
    )
    ax1.plot(capacity_df.index, capacity_df["total_value"] / 1000, linewidth=0.8, color="#1f77b4")
    ax1.set_ylabel("Portfolio Value (k EUR)")
    ax1.set_title("Portfolio Growth and Contribution Rebalancing Capacity")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Bottom: max drift correction per month (in pp)
    ax2.plot(
        capacity_df.index,
        capacity_df["max_drift_correction_pp"],
        linewidth=0.8,
        color="#ff7f0e",
        label="Max drift correction (pp/month)",
    )
    for thresh, color, ls in [(5.0, "red", "--"), (2.0, "orange", ":"), (1.0, "gray", "-.")]:
        ax2.axhline(thresh, color=color, linewidth=0.8, linestyle=ls, label=f"{thresh}pp threshold")
    ax2.set_ylabel("Max Drift Correction (pp/month)")
    ax2.set_xlabel("Date")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8)
    ax2.set_ylim(bottom=0)

    plt.tight_layout()
    fname = artifacts_dir / "contribution_capacity.png"
    plt.savefig(fname, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {fname}")


def print_summary(
    capacity_df: pd.DataFrame,
    crossovers: dict[str, str | None],
    by_year: dict[str, dict[str, float]],
) -> None:
    """Print human-readable summary to stdout."""
    print("\n" + "=" * 60)
    print("  CONTRIBUTION CAPACITY RESULTS")
    print("=" * 60)
    print(f"\n  Mean monthly contribution assumed: EUR {MEAN_CONTRIBUTION_EUR:.0f}")
    print(f"  Simulation period: {capacity_df.index[0].date()} to {capacity_df.index[-1].date()}")
    print(f"  Portfolio range: EUR {capacity_df['total_value'].min():,.0f} — "
          f"EUR {capacity_df['total_value'].max():,.0f}")
    print(f"\n  Crossover dates (when contribution capacity drops below threshold):")
    for threshold, dt in crossovers.items():
        print(f"    {threshold}: {dt or 'never crossed'}")

    print(f"\n  Year | Portfolio Start | Portfolio End | Max Corr (pp/month)")
    print("  " + "-" * 60)
    for year, stats in list(by_year.items())[:10]:  # first 10 years
        print(f"  {year} | {stats['portfolio_value_start']:>15,.0f} | "
              f"{stats['portfolio_value_end']:>13,.0f} | "
              f"{stats['mean_max_drift_correction_pp']:>18.2f}")
    if len(by_year) > 10:
        print("  ...")
        for year, stats in list(by_year.items())[-3:]:
            print(f"  {year} | {stats['portfolio_value_start']:>15,.0f} | "
                  f"{stats['portfolio_value_end']:>13,.0f} | "
                  f"{stats['mean_max_drift_correction_pp']:>18.2f}")


def main() -> None:
    """Entry point for contribution capacity exploration."""
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

    capacity_df = build_capacity_dataframe(result)
    print(f"  Capacity DataFrame: {len(capacity_df)} rows")

    crossovers = find_crossover_dates(capacity_df, thresholds_pct=[5.0, 2.0, 1.0, 0.5])
    by_year = analyze_by_year(capacity_df)

    print_summary(capacity_df, crossovers, by_year)

    print("\nSaving plots...")
    save_plots(capacity_df)

    results_dir = EXPERIMENT_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    output = results_dir / "contribution_capacity.json"
    output.write_text(json.dumps({
        "mean_contribution_eur": MEAN_CONTRIBUTION_EUR,
        "crossovers": crossovers,
        "by_year": by_year,
    }, indent=2))
    print(f"\nResults saved to {output}")


if __name__ == "__main__":
    main()
