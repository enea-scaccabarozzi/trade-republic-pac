from __future__ import annotations

import random
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport, calculate_deviations
from pac.backtester.config import BacktestConfig
from pac.backtester.data.models import PriceBar, PriceSeries
from pac.backtester.engine.actions import ExecutedTrade
from pac.backtester.engine.clock import SimulationClock
from pac.backtester.engine.market_context import BacktestMarketContext
from pac.backtester.engine.portfolio import SimulatedPortfolio, SimulatedPosition
from pac.backtester.results.models import (
    IndicatorDataPoint,
    IndicatorMeta,
    SignalRecord,
    StrategyEvent,
)
from pac.backtester.strategies.base import BacktestStrategy
from pac.config import Settings
from pac.config.models import SignalConfig
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.registry import SignalRegistry

log = structlog.get_logger()


class DayResult(BaseModel, frozen=True):
    """Snapshot of portfolio state at end of a trading day."""

    date: date
    total_value: Decimal
    allocations: dict[str, Decimal]  # asset_id → pct
    cash: Decimal


class IterationResult(BaseModel, frozen=True):
    """Result of a single Monte Carlo iteration."""

    iteration: int
    daily_values: list[DayResult]
    trades: list[ExecutedTrade]
    final_value: Decimal
    indicator_snapshots: dict[str, list[IndicatorDataPoint]] = {}
    signal_log: list[SignalRecord] = []
    strategy_events: list[StrategyEvent] = []


class SimulationResult(BaseModel, frozen=True):
    """Aggregated result across all MC iterations."""

    config: BacktestConfig
    iterations: list[IterationResult]


class BacktestSimulator:
    """Main simulation event loop with Monte Carlo iteration.

    For each MC iteration:
      1. Reset portfolio to initial state
      2. Sample a slippage value from uniform(min, max)
      3. For each trading day:
         a. Update prices (look up bar for each asset)
         b. Process any pending slippage-delayed actions
         c. If PAC date: execute PAC with current volumes
         d. Build PortfolioSnapshot (reuse live model)
         e. Compute DeviationReport (reuse analysis.deviation)
         f. Evaluate signal rules (reuse rules.registry)
         g. Feed signals to strategy → get actions
         h. Queue actions with slippage delay
         i. Record daily snapshot
    """

    def __init__(
        self,
        config: BacktestConfig,
        settings: Settings,
        price_data: dict[str, PriceSeries],
        signal_registry: SignalRegistry,
        strategy: BacktestStrategy[Any],
        *,
        rng_seed: int | None = None,
    ) -> None:
        self._config = config
        self._settings = settings
        self._price_data = price_data
        self._signal_registry = signal_registry
        self._strategy = strategy
        self._rng = random.Random(rng_seed)

        # Build asset_id → ticker mapping from settings
        self._asset_ticker: dict[str, str] = {
            a.id: a.ticker for a in settings.assets if a.ticker
        }
        # Reverse: ticker → asset_id (for price lookup)
        self._ticker_asset: dict[str, str] = {
            v: k for k, v in self._asset_ticker.items()
        }

        # Pre-build price index: asset_id → {date → PriceBar} for O(1) lookup
        self._price_index: dict[str, dict[date, PriceBar]] = {}
        for ticker, series in price_data.items():
            asset_id = self._ticker_asset.get(ticker)
            if asset_id:
                self._price_index[asset_id] = {bar.date: bar for bar in series.bars}

        # Pick a reference PriceSeries for trading days (use first)
        ref_ticker = next(iter(price_data))
        ref_series = price_data[ref_ticker].slice(config.start_date, config.end_date)
        self._clock = SimulationClock(
            series=ref_series,
            pac_execution_days=config.pac_execution_days,
        )

        # Initial PAC volumes: distribute monthly_contribution by target allocation
        targets = settings.target_allocations
        self._initial_pac_volumes: dict[str, Decimal] = {
            aid: (config.monthly_contribution * pct / Decimal(100))
            for aid, pct in targets.items()
        }

    def _build_portfolio(self) -> SimulatedPortfolio:
        """Create a fresh SimulatedPortfolio for an iteration."""
        assets = {
            a.id: SimulatedPosition(
                asset_id=a.id,
                isin=a.isin,
                name=a.name,
            )
            for a in self._settings.assets
        }
        return SimulatedPortfolio(
            assets=assets,
            cash=self._config.initial_cash,
            pac_volumes=dict(self._initial_pac_volumes),
            settlement_fee=self._config.settlement_fee,
            spread_bps=self._config.spread_bps,
            pac_execution_days=self._config.pac_execution_days,
        )

    def _get_prices_for_date(self, d: date) -> dict[str, PriceBar]:
        """Look up close prices for all assets on a given date.

        Uses the pre-built _price_index for O(1) lookup per asset.
        Returns asset_id → PriceBar mapping.
        """
        return {aid: index[d] for aid, index in self._price_index.items() if d in index}

    def _evaluate_signals(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        market_ctx: BacktestMarketContext | None = None,
    ) -> list[Signal]:
        """Run all configured signal rules against the snapshot."""
        signals: list[Signal] = []
        for sig_config in self._settings.signals:
            if sig_config.rule in self._signal_registry:
                result = self._signal_registry.evaluate_signal(
                    sig_config.rule,
                    sig_config.params,
                    report,
                    snapshot,
                    market_ctx=market_ctx,
                )
                signals.extend(result)
        return signals

    def _sample_slippage(self) -> int:
        """Sample a slippage delay from uniform distribution."""
        lo, hi = self._config.slippage_days
        return self._rng.randint(lo, hi)

    def _find_execution_date(self, d: date, slippage: int) -> date:
        """Find the trading day that is `slippage` trading days after d."""
        trading_days = list(self._clock)
        try:
            idx = trading_days.index(d)
        except ValueError:
            return d
        target_idx = min(idx + slippage, len(trading_days) - 1)
        return trading_days[target_idx]

    def run_iteration(self, iteration: int) -> IterationResult:
        """Run a single Monte Carlo iteration."""
        self._strategy.reset()
        portfolio = self._build_portfolio()
        slippage = self._sample_slippage()
        daily_values: list[DayResult] = []
        trading_days = list(self._clock)

        # Build indicator rule list once
        indicator_rules: list[tuple[Any, Any]] = []
        for sig_config in self._settings.signals:
            if sig_config.rule not in self._signal_registry:
                continue
            rule_cls = self._signal_registry.get_rule(sig_config.rule)
            rule = rule_cls()
            if rule.indicator_specs():
                params = rule_cls.params_model.model_validate(sig_config.params)
                indicator_rules.append((rule, params))

        indicator_accumulators: dict[str, list[IndicatorDataPoint]] = defaultdict(list)
        signal_log_entries: list[SignalRecord] = []
        strategy_events_acc: list[StrategyEvent] = []
        sample_counter = 0

        for d in trading_days:
            prices = self._get_prices_for_date(d)
            if not prices:
                continue

            # 1. Process pending slippage-delayed actions
            portfolio.process_pending_actions(d, prices)

            # 2. On PAC dates: let strategy adjust volumes, then execute PAC
            pac_day = self._clock.which_pac_day(d)
            if pac_day is not None:
                # Build snapshot for strategy before PAC execution
                pre_pac_snapshot = portfolio.snapshot(d, prices)
                pre_pac_report = calculate_deviations(
                    pre_pac_snapshot,
                    self._settings,
                )
                pac_adj = self._strategy.on_pac_date(
                    pre_pac_snapshot,
                    pre_pac_report,
                    d,
                    portfolio.pac_volumes,
                )
                if pac_adj is not None:
                    portfolio.apply_pac_adjustment(pac_adj)
                portfolio.execute_pac(
                    d,
                    prices,
                    self._config.monthly_contribution,
                    pac_day,
                )

            # 3. Build snapshot and compute deviations
            snapshot = portfolio.snapshot(d, prices)
            report = calculate_deviations(snapshot, self._settings)

            # 3.5. Build market context for this date
            market_ctx = BacktestMarketContext(
                price_data=self._price_data,
                current_date=d,
                ticker_map=self._asset_ticker,
            )

            # 4. Evaluate signal rules
            signals = self._evaluate_signals(snapshot, report, market_ctx=market_ctx)

            # Log all signals from this day
            for sig in signals:
                signal_log_entries.append(
                    SignalRecord(
                        date=d,
                        rule_name=sig.name,
                        severity=sig.severity.value,
                        message=sig.message,
                        metadata=sig.metadata,
                    )
                )

            # 5. Feed signals to strategy → get actions
            if signals:
                actions = self._strategy.on_signals(
                    signals,
                    snapshot,
                    report,
                    d,
                )
                # 6. Queue actions with slippage delay
                for action in actions:
                    execute_on = self._find_execution_date(d, slippage)
                    portfolio.queue_action(action, emitted_on=d, execute_on=execute_on)

            # Drain strategy events (always, not just when signals fire)
            strategy_events_acc.extend(self._strategy.drain_events())

            # 7. Record daily snapshot
            asset_ids = [a.id for a in self._settings.assets]
            allocs = snapshot.allocations(asset_ids)
            daily_values.append(
                DayResult(
                    date=d,
                    total_value=snapshot.total_value,
                    allocations={aid: allocs[aid].actual_pct for aid in asset_ids},
                    cash=portfolio.cash,
                ),
            )

            # 8. Indicator sampling (every 5 trading days ~ weekly)
            sample_counter += 1
            if sample_counter % 5 == 0:
                for rule, params in indicator_rules:
                    result = rule.compute_indicators(
                        params,
                        market_ctx=market_ctx,
                    )
                    if result is None:
                        continue
                    for suffix, value in result.values.items():
                        key = f"{rule.name}.{suffix}"
                        indicator_accumulators[key].append(
                            IndicatorDataPoint(date=d, value=value),
                        )

        return IterationResult(
            iteration=iteration,
            daily_values=daily_values,
            trades=portfolio.trade_log,
            final_value=(
                daily_values[-1].total_value
                if daily_values
                else self._config.initial_cash
            ),
            indicator_snapshots=dict(indicator_accumulators),
            signal_log=signal_log_entries,
            strategy_events=strategy_events_acc,
        )

    def run(self) -> SimulationResult:
        """Run all Monte Carlo iterations."""
        log.info(
            "backtest_start",
            strategy=self._config.strategy,
            iterations=self._config.monte_carlo_iterations,
            start=str(self._config.start_date),
            end=str(self._config.end_date),
        )

        iterations: list[IterationResult] = []
        for i in range(self._config.monte_carlo_iterations):
            result = self.run_iteration(i)
            iterations.append(result)
            if (i + 1) % 10 == 0:
                log.debug("backtest_progress", completed=i + 1)

        log.info("backtest_complete", iterations=len(iterations))
        return SimulationResult(config=self._config, iterations=iterations)


def collect_indicator_meta(
    signal_configs: list[SignalConfig],
    registry: SignalRegistry,
) -> list[IndicatorMeta]:
    """Build IndicatorMeta list from all configured rules' indicator_specs()."""
    metas: list[IndicatorMeta] = []
    for sig_config in signal_configs:
        if sig_config.rule not in registry:
            continue
        rule_cls = registry.get_rule(sig_config.rule)
        rule = rule_cls()
        for spec in rule.indicator_specs():
            full_key = f"{rule.name}.{spec.key_suffix}"
            companion_keys = [f"{rule.name}.{s}" for s in spec.companion_suffixes]
            metas.append(
                IndicatorMeta(
                    key=full_key,
                    display_name=spec.display_name,
                    group=spec.group,
                    kind=spec.kind,
                    unit=spec.unit,
                    thresholds=spec.thresholds,
                    companion_keys=companion_keys,
                    rule_name=rule.name,
                )
            )
    return metas
