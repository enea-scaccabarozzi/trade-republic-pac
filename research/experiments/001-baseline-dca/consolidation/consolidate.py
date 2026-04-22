"""Consolidation: quick deterministic simulation of baseline DCA.

Runs a single N=1, zero-slippage simulation to verify the strategy
works correctly and produces sensible equity curves. Uses ResearchContext
for data loading, then builds BacktestSimulator directly to configure
pac_execution_days=[16] (monthly on the 16th only).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_DIR.parents[2] / "src"))
sys.path.insert(0, str(EXPERIMENT_DIR))

# Register experiment-local strategy BEFORE any discovery call
from strategies.baseline_dca import BaselineDCA, BaselineDCAParams  # noqa: E402

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import BacktestSimulator
from pac.backtester.metrics.twrr import compute_mwrr, compute_twrr
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


def run_quick_test(ctx: ResearchContext) -> None:
    """Run N=1 deterministic simulation and print summary."""
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

    print(f"Simulation period: {ctx.data_start} to {ctx.data_end}")
    print(f"Config: PAC on 16th, contribution U(500,700), initial_cash=0")
    print(f"Running quick-test (N=1, zero slippage)...")

    result = simulator.run_iteration(0)

    # Summary
    final_value = result.final_value
    total_invested = sum(
        t.amount_eur for t in result.trades if t.direction == "buy"
    )
    total_fees = sum(t.fee for t in result.trades)
    total_tax = result.total_tax_paid
    num_trades = len(result.trades)
    trading_days = len(result.daily_values)

    print(f"\n{'='*50}")
    print(f"  QUICK-TEST RESULTS")
    print(f"{'='*50}")
    print(f"  Trading days:    {trading_days}")
    print(f"  Total trades:    {num_trades}")
    print(f"  Total invested:  EUR {total_invested:,.2f}")
    print(f"  Total fees:      EUR {total_fees:,.2f}")
    print(f"  Total tax:       EUR {total_tax:,.2f}")
    print(f"  Final value:     EUR {final_value:,.2f}")
    gain = final_value - total_invested
    gain_pct = (gain / total_invested * 100) if total_invested > 0 else 0
    print(f"  Gain:            EUR {gain:,.2f} ({gain_pct:+.1f}%)")

    # Equity curve summary (first, last, min, max)
    values = [dv.total_value for dv in result.daily_values]
    dates = [dv.date for dv in result.daily_values]
    if values:
        min_val = min(values)
        max_val = max(values)
        min_idx = values.index(min_val)
        max_idx = values.index(max_val)
        print(f"\n  Equity curve:")
        print(f"    First:  EUR {values[0]:>12,.2f}  ({dates[0]})")
        print(f"    Min:    EUR {min_val:>12,.2f}  ({dates[min_idx]})")
        print(f"    Max:    EUR {max_val:>12,.2f}  ({dates[max_idx]})")
        print(f"    Last:   EUR {values[-1]:>12,.2f}  ({dates[-1]})")

    # Compute metrics
    metrics = ctx.compute_metrics(result)
    print(f"\n  Metrics:")
    for name, value in sorted(metrics.items()):
        print(f"    {name:<15} {value:>10.4f}")

    twrr = compute_twrr(result)
    mwrr = compute_mwrr(result, initial_cash=Decimal("0"))
    print(f"\n  Return metrics (contribution-adjusted):")
    print(f"    {'TWRR (annualized)':<20} {twrr:>10.4f}")
    print(f"    {'MWRR (annualized)':<20} {mwrr:>10.4f}")

    # Save quick-test results
    output = EXPERIMENT_DIR / "results" / "quick_test.json"
    output.parent.mkdir(exist_ok=True)
    summary = {
        "period": f"{ctx.data_start} to {ctx.data_end}",
        "trading_days": trading_days,
        "total_trades": num_trades,
        "total_invested": str(total_invested),
        "total_fees": str(total_fees),
        "total_tax": str(total_tax),
        "final_value": str(final_value),
        "gain_pct": round(float(gain_pct), 2),
        "metrics": {k: round(v, 4) for k, v in metrics.items()},
        "twrr": round(twrr, 4),
        "mwrr": round(mwrr, 4),
    }
    output.write_text(json.dumps(summary, indent=2))
    print(f"\n  Results saved to {output}")


def main():
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

    print(f"\nData range: {ctx.data_start} to {ctx.data_end}")
    for asset_id, series in ctx.prices.items():
        print(f"  {asset_id}: {series.start_date} to {series.end_date} ({len(series.bars)} bars)")

    run_quick_test(ctx)


if __name__ == "__main__":
    main()
