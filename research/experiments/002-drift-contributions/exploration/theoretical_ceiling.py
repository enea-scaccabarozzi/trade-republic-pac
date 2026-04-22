"""Theoretical ceiling: oracle contribution steering upper bound.

Phase 1 (Exploration) — Script 4 of 4.

Before investing time in a specific drift-steering strategy, this script
answers: how much improvement is even possible? It implements an oracle
strategy that allocates each month's contribution perfectly (with full
knowledge of actual drift on the PAC date) toward underweight assets
proportional to their shortfall. This is the theoretical maximum gain
from contribution steering — no real strategy can exceed it.

Key question: if TWRR improvement < 0.1pp, contribution steering is
unlikely to be worth the engineering effort.

Results saved to: results/theoretical_ceiling.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EXPERIMENT_DIR.parents[2] / "src"
BASELINE_STRATEGIES = EXPERIMENT_DIR.parents[0] / "001-baseline-dca" / "strategies"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASELINE_STRATEGIES))

import pandas as pd
from baseline_dca import BaselineDCA, BaselineDCAParams  # noqa: E402
from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport
from pac.backtester.config import BacktestConfig
from pac.backtester.engine.actions import Action, PacAdjustment
from pac.backtester.engine.simulator import BacktestSimulator, IterationResult
from pac.backtester.metrics.returns import equity_to_returns
from pac.backtester.metrics.twrr import compute_mwrr, compute_twrr
from pac.backtester.research.context import ResearchContext
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry


class OracleContributionParams(BaseModel, frozen=True):
    """No tunable parameters — oracle has full information."""


class OracleContributionStrategy(BacktestStrategy[OracleContributionParams]):
    """Oracle strategy: allocate contributions toward underweight assets.

    On each PAC date, examines the actual allocation drift and redirects
    contributions proportionally toward assets that are underweight relative
    to their targets. If all assets are at or above their target, falls back
    to static target-proportional allocation.

    This is the theoretical ceiling for drift-based contribution steering:
    it acts with perfect information (current drift on the PAC date itself)
    and zero lag. No real strategy can outperform this oracle.
    """

    name: ClassVar[str] = "oracle_contribution"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        """Oracle ignores signals — contribution steering only, no rebalancing."""
        return []

    def on_pac_date(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
        current_pac_volumes: dict[str, Decimal],
    ) -> PacAdjustment | None:
        """Redirect contributions toward underweight assets proportional to shortfall.

        The total contribution budget is preserved (sum of new_volumes == sum of
        current_pac_volumes). Only the distribution across assets changes.

        Args:
            snapshot: Current portfolio state.
            report: Deviation analysis for current portfolio.
            current_date: PAC execution date.
            current_pac_volumes: Current PAC volumes per asset (EUR).

        Returns:
            PacAdjustment with redistributed volumes, or None if all assets are
            at or above target (no underweight assets to steer toward).
        """
        # Total monthly budget to distribute
        total_budget = sum(current_pac_volumes.values())
        if total_budget <= 0:
            return None

        # Compute shortfalls: how much each asset is below its target (pp)
        shortfalls: dict[str, Decimal] = {}
        for asset_id, alloc in report.deviations.items():
            shortfall = alloc.target_pct - alloc.actual_pct
            if shortfall > Decimal("0"):
                shortfalls[asset_id] = shortfall

        if not shortfalls:
            # All assets at or above target — static allocation (no adjustment)
            return None

        # Distribute budget proportional to shortfalls
        total_shortfall = sum(shortfalls.values())
        new_volumes: dict[str, Decimal] = {}
        allocated = Decimal("0")

        # Sort to make allocation deterministic
        sorted_assets = sorted(shortfalls.keys())
        for i, asset_id in enumerate(sorted_assets):
            if i == len(sorted_assets) - 1:
                # Last asset gets the remainder to avoid rounding drift
                new_volumes[asset_id] = total_budget - allocated
            else:
                share = shortfalls[asset_id] / total_shortfall
                amount = (total_budget * share).quantize(Decimal("0.01"))
                new_volumes[asset_id] = amount
                allocated += amount

        # Assets with no shortfall get 0 contribution this month
        for asset_id in current_pac_volumes:
            if asset_id not in new_volumes:
                new_volumes[asset_id] = Decimal("0")

        return PacAdjustment(new_volumes=new_volumes)


def build_signal_registry(ctx: ResearchContext) -> SignalRegistry:
    """Build a SignalRegistry from context settings."""
    rule_classes = discover_rules()
    registry = SignalRegistry()
    for sig_cfg in ctx.settings.signals:
        if sig_cfg.rule in rule_classes:
            rule_cls = rule_classes[sig_cfg.rule]
            registry.register(rule_cls)
    return registry


def build_backtest_config(ctx: ResearchContext) -> BacktestConfig:
    """Build BacktestConfig shared by both baseline and oracle simulations."""
    return BacktestConfig(
        strategy="baseline_dca",  # placeholder — overridden by strategy instance
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


def run_simulation(
    ctx: ResearchContext,
    strategy: BacktestStrategy[BaseModel],
    config: BacktestConfig,
) -> IterationResult:
    """Run a single iteration with the given strategy.

    Args:
        ctx: Research context with price data and settings.
        strategy: Instantiated BacktestStrategy.
        config: BacktestConfig for the simulation.

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


def compute_full_metrics(result: IterationResult) -> dict[str, float]:
    """Compute TWRR, MWRR, and quantstats metrics for a result.

    Args:
        result: Single iteration result.

    Returns:
        Dict with keys: twrr, mwrr, sharpe, sortino, max_drawdown, calmar, volatility.
    """
    try:
        import quantstats as qs
    except ImportError:
        print("  WARNING: quantstats not available — skipping Sharpe/Sortino/Calmar")
        return {
            "twrr": compute_twrr(result),
            "mwrr": compute_mwrr(result, initial_cash=Decimal("0")),
        }

    returns = equity_to_returns(result)
    metrics: dict[str, float] = {
        "twrr": compute_twrr(result),
        "mwrr": compute_mwrr(result, initial_cash=Decimal("0")),
    }
    if not returns.empty:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metrics["sharpe"] = float(qs.stats.sharpe(returns, periods=252))
            metrics["sortino"] = float(qs.stats.sortino(returns, periods=252))
            metrics["max_drawdown"] = float(qs.stats.max_drawdown(returns))
            metrics["calmar"] = float(qs.stats.calmar(returns))
            metrics["volatility"] = float(qs.stats.volatility(returns, periods=252))
    return metrics


def print_comparison_table(
    baseline_metrics: dict[str, float],
    oracle_metrics: dict[str, float],
) -> None:
    """Print side-by-side comparison of baseline vs oracle metrics."""
    print("\n" + "=" * 65)
    print("  THEORETICAL CEILING — BASELINE vs ORACLE COMPARISON")
    print("=" * 65)
    print(f"\n  {'Metric':<20} {'Baseline':>12} {'Oracle':>12} {'Delta':>10}")
    print("  " + "-" * 57)
    all_metrics = sorted(set(baseline_metrics) | set(oracle_metrics))
    for metric in all_metrics:
        b = baseline_metrics.get(metric, float("nan"))
        o = oracle_metrics.get(metric, float("nan"))
        delta = o - b if (b == b and o == o) else float("nan")
        b_str = f"{b:.4f}" if b == b else "n/a"
        o_str = f"{o:.4f}" if o == o else "n/a"
        d_str = f"{delta:+.4f}" if delta == delta else "n/a"
        print(f"  {metric:<20} {b_str:>12} {o_str:>12} {d_str:>10}")

    # Interpretation
    twrr_delta = oracle_metrics.get("twrr", float("nan")) - baseline_metrics.get("twrr", float("nan"))
    print(f"\n  TWRR improvement from oracle steering: {twrr_delta:+.4f} ({twrr_delta*100:+.2f}%)")
    if twrr_delta < 0.001:
        print("  *** CEILING TOO LOW: <0.1pp improvement → steering unlikely to be worth it ***")
    elif twrr_delta < 0.005:
        print("  NOTE: Modest ceiling (0.1-0.5pp) — only a well-tuned strategy can capture it")
    else:
        print("  PASS: Meaningful ceiling — real strategies have room to improve")


def main() -> None:
    """Entry point for theoretical ceiling exploration."""
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
    ctx.register_strategy("oracle_contribution", OracleContributionStrategy)

    print(f"Data range: {ctx.data_start} to {ctx.data_end}")
    config = build_backtest_config(ctx)

    print("\nRunning baseline simulation (N=1, deterministic)...")
    baseline_result = run_simulation(ctx, BaselineDCA(BaselineDCAParams()), config)
    print(f"  Baseline: {len(baseline_result.daily_values)} days, "
          f"final value EUR {baseline_result.final_value:,.2f}")

    print("Running oracle simulation (N=1, deterministic)...")
    oracle_result = run_simulation(
        ctx,
        OracleContributionStrategy(OracleContributionParams()),
        config,
    )
    print(f"  Oracle:   {len(oracle_result.daily_values)} days, "
          f"final value EUR {oracle_result.final_value:,.2f}")

    print("\nComputing metrics...")
    baseline_metrics = compute_full_metrics(baseline_result)
    oracle_metrics = compute_full_metrics(oracle_result)

    print_comparison_table(baseline_metrics, oracle_metrics)

    # Save results
    results_dir = EXPERIMENT_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    output = results_dir / "theoretical_ceiling.json"
    output.write_text(json.dumps({
        "period": f"{ctx.data_start} to {ctx.data_end}",
        "baseline": {
            "final_value": str(baseline_result.final_value),
            "metrics": {k: round(v, 6) for k, v in baseline_metrics.items() if v == v},
        },
        "oracle": {
            "final_value": str(oracle_result.final_value),
            "metrics": {k: round(v, 6) for k, v in oracle_metrics.items() if v == v},
        },
        "delta": {
            k: round(oracle_metrics.get(k, float("nan")) - baseline_metrics.get(k, float("nan")), 6)
            for k in set(baseline_metrics) | set(oracle_metrics)
            if (
                oracle_metrics.get(k, float("nan")) == oracle_metrics.get(k, float("nan"))
                and baseline_metrics.get(k, float("nan")) == baseline_metrics.get(k, float("nan"))
            )
        },
    }, indent=2))
    print(f"\nResults saved to {output}")


if __name__ == "__main__":
    main()
