from __future__ import annotations

import os
import random
from collections import defaultdict
from collections.abc import Callable
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
from pac.backtester.engine.contributions import resolve_contribution
from pac.backtester.engine.market_context import BacktestMarketContext
from pac.backtester.engine.portfolio import SimulatedPortfolio, SimulatedPosition
from pac.backtester.engine.tax import AssetTaxMeta, resolve_tax_regime
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
    total_tax_paid: Decimal = Decimal(0)
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

        # Resolve tax regime
        self._tax_regime = resolve_tax_regime(config.tax_regime, config.tax_params)

        # Build asset tax metadata from settings
        self._asset_tax_meta: dict[str, AssetTaxMeta] = {
            a.id: AssetTaxMeta(**a.tax_meta) for a in settings.assets
        }

        # Initial PAC volumes: distribute monthly_contribution by target allocation.
        # For stochastic ContributionConfig, seed with the mean amount; Task 7 wires
        # per-execution sampling so this seed is overwritten at each PAC date.
        seed_contribution: Decimal = (
            config.monthly_contribution
            if isinstance(config.monthly_contribution, Decimal)
            else (config.monthly_contribution.min + config.monthly_contribution.max)
            / Decimal("2")
        )
        targets = settings.target_allocations
        self._initial_pac_volumes: dict[str, Decimal] = {
            aid: (seed_contribution * pct / Decimal(100))
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
            tax_regime=self._tax_regime,
            asset_tax_meta=self._asset_tax_meta,
            rng=self._rng,
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
        self._tax_regime.reset()
        portfolio = self._build_portfolio()
        slippage = self._sample_slippage()
        daily_values: list[DayResult] = []
        trading_days = list(self._clock)
        contribution_dist = resolve_contribution(self._config.monthly_contribution)
        sampled_months: dict[tuple[int, int], Decimal] = {}

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
                month_key = (d.year, d.month)
                if month_key not in sampled_months:
                    sampled_months[month_key] = contribution_dist.sample(self._rng)
                monthly_amount = sampled_months[month_key]

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
                    monthly_amount,
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

        total_tax = sum((t.tax for t in portfolio.trade_log), Decimal(0))
        return IterationResult(
            iteration=iteration,
            daily_values=daily_values,
            trades=portfolio.trade_log,
            final_value=(
                daily_values[-1].total_value
                if daily_values
                else self._config.initial_cash
            ),
            total_tax_paid=total_tax,
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


def _iteration_worker(
    config: BacktestConfig,
    settings: Settings,
    price_data: dict[str, PriceSeries],
    signal_configs: list[SignalConfig],
    strategy_name: str,
    strategy_params: dict[str, Any],
    iteration: int,
    seed: int,
) -> IterationResult:
    """Top-level picklable function for parallel MC execution.

    Reconstructs registry and strategy from scratch in each worker process
    since those objects are not picklable.

    Args:
        config: Backtest configuration.
        settings: Application settings.
        price_data: Pre-loaded price series keyed by ticker.
        signal_configs: Signal rule configurations (unused here; registry
            is rebuilt from discovery).
        strategy_name: Name of the strategy to instantiate.
        strategy_params: Raw params dict to validate against params_model.
        iteration: Iteration index (determines seed offset).
        seed: Base RNG seed; worker uses seed + iteration.

    Returns:
        IterationResult for this single iteration.
    """
    from pac.backtester.strategies.discovery import discover_strategies
    from pac.rules.discovery import discover_rules

    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)

    strategies = discover_strategies()
    strategy_cls = strategies[strategy_name]
    params = strategy_cls.params_model.model_validate(strategy_params)
    strategy = strategy_cls(params)

    simulator = BacktestSimulator(
        config,
        settings,
        price_data,
        registry,
        strategy,
        rng_seed=seed + iteration,
    )
    return simulator.run_iteration(iteration)


def run_iterations_parallel(
    config: BacktestConfig,
    settings: Settings,
    price_data: dict[str, PriceSeries],
    registry: SignalRegistry,
    strategy: BacktestStrategy[Any],
    *,
    seed: int | None = None,
    max_workers: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[IterationResult]:
    """Run Monte Carlo iterations in parallel using ProcessPoolExecutor.

    For N=1 (quick-test mode), runs in-process to avoid pool overhead.
    For N>1, dispatches each iteration to a separate worker process, with
    each worker receiving seed + iteration as its RNG seed — matching the
    sequential baseline.

    Args:
        config: Backtest configuration (monte_carlo_iterations controls N).
        settings: Application settings.
        price_data: Pre-loaded price series keyed by ticker.
        registry: Signal registry (used only for N=1 in-process path).
        strategy: Instantiated strategy (used only for N=1 in-process path).
        seed: Base RNG seed; iteration i uses seed + i.
        max_workers: Maximum worker processes. Defaults to cpu_count.
        on_progress: Called after each completed iteration with (done, total).

    Returns:
        List of IterationResult, one per MC iteration (order may differ from
        sequential; sort by .iteration if order matters).
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    n = config.monte_carlo_iterations
    base_seed = seed or 0

    if n <= 1:
        sim = BacktestSimulator(
            config,
            settings,
            price_data,
            registry,
            strategy,
            rng_seed=base_seed,
        )
        result = sim.run_iteration(0)
        if on_progress:
            on_progress(1, 1)
        return [result]

    workers = min(
        max_workers or os.cpu_count() or 4,
        n,
    )

    results: list[IterationResult] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _iteration_worker,
                config,
                settings,
                price_data,
                settings.signals,
                config.strategy,
                config.strategy_params,
                i,
                base_seed,
            ): i
            for i in range(n)
        }
        for future in as_completed(futures):
            results.append(future.result())
            if on_progress:
                on_progress(len(results), n)

    return results


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
