"""ResearchContext — zero-ceremony research API.

Thin facade over MarketDataProvider, IndicatorRegistry, BacktestSimulator,
and the config loader that replaces ~40 lines of boilerplate with a single
``ResearchContext.from_config()`` call.
"""

from __future__ import annotations

__all__ = ["ResearchContext"]

import itertools
import math
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import (
    BacktestSimulator,
    IterationResult,
    SimulationResult,
)
from pac.backtester.research.events import EventCalendar
from pac.backtester.research.events_builtin import BUILTIN_CALENDARS
from pac.backtester.research.indicators import (
    CompositeResult,
    IndicatorRegistry,
    IndicatorResult,
)
from pac.backtester.research.models import (
    ComparisonTable,
    EventAnalysisResult,
    EventMetrics,
    OOSResult,
    QuantstatsMetrics,
    SweepResult,
    VariantResult,
    WalkForwardResult,
    WFWindow,
)
from pac.backtester.strategies.base import BacktestStrategy
from pac.backtester.strategies.discovery import discover_strategies
from pac.config.loader import load_config
from pac.config.models import Settings
from pac.models.market_data import PriceSeries
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry


def _is_nan(value: float) -> bool:
    """Check if a float value is NaN."""
    return math.isnan(value)


class ResearchContext:
    """Zero-ceremony research API — thin facade over data, indicators, simulation."""

    def __init__(
        self,
        settings: Settings,
        price_data: dict[str, PriceSeries],
        ticker_price_data: dict[str, PriceSeries],
        registry: IndicatorRegistry,
    ) -> None:
        self._settings = settings
        self._price_data = price_data
        self._ticker_price_data = ticker_price_data
        self._registry = registry
        # Date range intersection (common overlap across all assets)
        self._data_start = max(s.bars[0].date for s in price_data.values())
        self._data_end = min(s.bars[-1].date for s in price_data.values())
        # Lazy caches for discovery results
        self._rules: SignalRegistry | None = None
        self._strategies: dict[str, type[BacktestStrategy[Any]]] | None = None

    # ── Factory ─────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config_path: str | Path,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        packs: list[str] | None = None,
    ) -> ResearchContext:
        """Build a ResearchContext from a YAML config file.

        Loads settings, fetches price data for all assets (building both
        asset_id-keyed and ticker-keyed dicts simultaneously), creates an
        empty IndicatorRegistry, and optionally loads indicator packs.

        Args:
            config_path: Path to pac.yaml configuration file.
            start_date: Start of price data window. Defaults to 30 years ago.
            end_date: End of price data window. Defaults to today.
            packs: Optional list of indicator pack names to register.

        Returns:
            A fully initialized ResearchContext.

        Raises:
            ValueError: If any asset is missing a ``ticker`` field.
            FileNotFoundError: If config file doesn't exist.
        """
        from pac.backtester.data.provider import MarketDataProvider

        settings = load_config(Path(config_path))

        # Validate all assets have tickers
        missing = [a for a in settings.assets if not a.ticker]
        if missing:
            names = ", ".join(a.id for a in missing)
            raise ValueError(
                f"Assets missing 'ticker' field: {names}\n"
                "Add 'ticker: SWRD.SW' to each asset in pac.yaml."
            )

        # Default date range: 30-year lookback → today
        if start_date is None:
            start_date = date.today() - timedelta(days=30 * 365)
        if end_date is None:
            end_date = date.today()

        # Fetch price data — build both dicts in a single asset loop
        provider = MarketDataProvider()
        ticker_price_data: dict[str, PriceSeries] = {}
        asset_price_data: dict[str, PriceSeries] = {}
        for a in settings.assets:
            if a.ticker is None:
                continue  # already validated above, but mypy needs this
            series = provider.fetch_with_proxy(
                ticker=a.ticker,
                start=start_date,
                end=end_date,
                proxy_chain=a.proxy_chain or None,
                primary_currency=a.currency,
            )
            ticker_price_data[a.ticker] = series
            asset_price_data[a.id] = series

        # Create empty registry and optionally load packs
        registry = IndicatorRegistry(asset_price_data)
        if packs:
            for pack_name in packs:
                registry.register_pack(pack_name)

        return cls(settings, asset_price_data, ticker_price_data, registry)

    # ── Data access ─────────────────────────────────────────

    @property
    def prices(self) -> dict[str, PriceSeries]:
        """Asset ID → PriceSeries mapping for direct data access."""
        return self._price_data

    @property
    def settings(self) -> Settings:
        """The loaded Settings from pac.yaml."""
        return self._settings

    @property
    def calendars(self) -> dict[str, EventCalendar]:
        """Built-in event calendars (crises, bull_runs, corrections, rate_regimes)."""
        return dict(BUILTIN_CALENDARS)

    @property
    def indicators(self) -> IndicatorRegistry:
        """The underlying indicator registry (for advanced use)."""
        return self._registry

    def to_dataframe(self, asset_id: str) -> Any:
        """Convert a PriceSeries to a pandas DataFrame.

        Lazy-imports pandas. Raises ImportError with a clear message
        if pandas is not installed.

        Args:
            asset_id: Key in ``self.prices`` (e.g., ``"stocks"``).

        Returns:
            pandas DataFrame with date index and float OHLCV columns.

        Raises:
            KeyError: If asset_id is not in the price data.
            ImportError: If pandas is not installed.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install with: pip install pandas"
            ) from None

        if asset_id not in self._price_data:
            available = sorted(self._price_data.keys())
            raise KeyError(f"Unknown asset_id {asset_id!r}. Available: {available}")

        series = self._price_data[asset_id]
        rows = [
            {
                "date": bar.date,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": int(bar.volume),
            }
            for bar in series.bars
        ]
        df: Any = pd.DataFrame(rows)
        df = df.set_index("date")
        return df

    # ── Indicator convenience ───────────────────────────────

    def indicator(
        self,
        name: str,
        target_date: date,
        *,
        asset: str | None = None,
        **kwargs: object,
    ) -> IndicatorResult:
        """Compute a registered indicator for a single date.

        Delegates to ``IndicatorRegistry.compute()``.
        """
        return self._registry.compute(name, target_date, asset=asset, **kwargs)

    def indicator_series(
        self,
        name: str,
        start: date,
        end: date,
        *,
        asset: str | None = None,
        **kwargs: object,
    ) -> list[tuple[date, IndicatorResult]]:
        """Compute indicator across a date range.

        Delegates to ``IndicatorRegistry.series()``.
        """
        return self._registry.series(name, start, end, asset=asset, **kwargs)

    def register_pack(self, pack_name: str) -> None:
        """Load a named indicator pack into the registry."""
        self._registry.register_pack(pack_name)

    def register_indicator(
        self,
        name: str,
        fn: Callable[..., IndicatorResult],
        *,
        asset: str = "stocks",
        assets: list[str] | None = None,
        lookback_days: int = 252,
    ) -> None:
        """Register a custom indicator function."""
        self._registry.register(
            name,
            fn,
            asset=asset,
            assets=assets,
            lookback_days=lookback_days,
        )

    def composite_series(
        self,
        indicators: list[str | tuple[str, dict[str, object]]],
        *,
        min_active: int,
        start: date,
        end: date,
        thresholds: dict[str, Callable[[IndicatorResult], bool]] | None = None,
    ) -> list[CompositeResult]:
        """Compute N-of-M composite voting across registered indicators.

        Delegates to IndicatorRegistry.composite_series().
        """
        return self._registry.composite_series(
            indicators,
            min_active=min_active,
            start=start,
            end=end,
            thresholds=thresholds,
        )

    # ── Simulation ──────────────────────────────────────────

    def simulate(
        self,
        strategy: str,
        params: dict[str, Any] | None = None,
        *,
        tax_regime: str = "italian",
        tax_params: dict[str, Any] | None = None,
        monthly_contribution: Decimal | dict[str, Any] | None = None,
    ) -> IterationResult:
        """Run a quick-test simulation (N=1, deterministic, no slippage).

        Args:
            strategy: Strategy name (must be a discovered BacktestStrategy).
            params: Strategy parameters dict (validated against params_model).
            tax_regime: Tax regime to apply (``"italian"`` or ``"none"``).
                Defaults to ``"italian"``.
            tax_params: Regime-specific tax parameters. Defaults to ``{}``.
            monthly_contribution: Monthly contribution amount or
                ``ContributionConfig``-compatible dict. When ``None``,
                the ``BacktestConfig`` default (500 EUR) is used.

        Returns:
            Single IterationResult.

        Raises:
            ValueError: If strategy name is unknown.
        """
        config_kwargs: dict[str, Any] = {
            "strategy": strategy,
            "strategy_params": params or {},
            "start_date": self._data_start,
            "end_date": self._data_end,
            "monte_carlo_iterations": 1,
            "slippage_days": (0, 0),
            "tax_regime": tax_regime,
            "tax_params": tax_params or {},
        }
        if monthly_contribution is not None:
            config_kwargs["monthly_contribution"] = monthly_contribution
        config = BacktestConfig(**config_kwargs)
        strategy_instance = self._resolve_strategy(strategy, params)
        signal_registry = self._signal_registry()
        simulator = BacktestSimulator(
            config,
            self._settings,
            self._ticker_price_data,
            signal_registry,
            strategy_instance,
            rng_seed=42,
        )
        return simulator.run_iteration(0)

    def simulate_mc(
        self,
        strategy: str,
        params: dict[str, Any] | None = None,
        *,
        iterations: int = 50,
        seed: int | None = None,
        slippage_days: tuple[int, int] = (0, 3),
        tax_regime: str = "italian",
        tax_params: dict[str, Any] | None = None,
        monthly_contribution: Decimal | dict[str, Any] | None = None,
    ) -> SimulationResult:
        """Run a full Monte Carlo simulation.

        Args:
            strategy: Strategy name (must be a discovered BacktestStrategy).
            params: Strategy parameters dict.
            iterations: Number of MC iterations.
            seed: RNG seed for reproducibility.
            slippage_days: (min, max) human delay range in days.
            tax_regime: Tax regime to apply (``"italian"`` or ``"none"``).
                Defaults to ``"italian"``.
            tax_params: Regime-specific tax parameters. Defaults to ``{}``.
            monthly_contribution: Monthly contribution amount or
                ``ContributionConfig``-compatible dict. When ``None``,
                the ``BacktestConfig`` default (500 EUR) is used.

        Returns:
            SimulationResult with all iterations.

        Raises:
            ValueError: If strategy name is unknown.
        """
        config_kwargs: dict[str, Any] = {
            "strategy": strategy,
            "strategy_params": params or {},
            "start_date": self._data_start,
            "end_date": self._data_end,
            "monte_carlo_iterations": iterations,
            "slippage_days": slippage_days,
            "tax_regime": tax_regime,
            "tax_params": tax_params or {},
        }
        if monthly_contribution is not None:
            config_kwargs["monthly_contribution"] = monthly_contribution
        config = BacktestConfig(**config_kwargs)
        strategy_instance = self._resolve_strategy(strategy, params)
        signal_registry = self._signal_registry()
        simulator = BacktestSimulator(
            config,
            self._settings,
            self._ticker_price_data,
            signal_registry,
            strategy_instance,
            rng_seed=seed,
        )
        return simulator.run()

    # ── Metrics / Compare / Sweep ───────────────────────────

    def compute_metrics(
        self,
        result: IterationResult,
        metric_names: list[str] | None = None,
    ) -> dict[str, float]:
        """Compute metrics from a single IterationResult.

        Converts the equity curve to daily returns via equity_to_returns(),
        then calls MetricsCalculator.compute_iteration() which returns
        dict[str, float] directly.

        Args:
            result: A single iteration result with equity curve data.
            metric_names: Metrics to compute. Defaults to
                ["sharpe", "cagr", "max_drawdown"].

        Returns:
            Dict of metric_name → float value.
        """
        from pac.backtester.metrics.calculator import MetricsCalculator
        from pac.backtester.metrics.returns import equity_to_returns

        names = metric_names or ["sharpe", "cagr", "max_drawdown"]
        calc = MetricsCalculator(names)
        returns = equity_to_returns(result)
        return calc.compute_iteration(returns)

    @staticmethod
    def _auto_label(strategy: str, params: dict[str, Any]) -> str:
        """Generate a label like ``crisis_exploit[dd=-20, cool=60]``."""
        if not params:
            return strategy
        abbrevs = [f"{k}={v}" for k, v in list(params.items())[:3]]
        return f"{strategy}[{', '.join(abbrevs)}]"

    def compare(
        self,
        variants: list[dict[str, Any]],
        *,
        metrics: list[str] | None = None,
        tax_regime: str = "italian",
        tax_params: dict[str, Any] | None = None,
        monthly_contribution: Decimal | dict[str, Any] | None = None,
    ) -> ComparisonTable:
        """Compare multiple strategy+params combinations.

        Each variant dict must have:
          - "strategy": str (required)
          - "params": dict (optional, defaults to {})
          - "label": str (optional, auto-generated if missing)

        Runs simulate() for each variant (quick-test: N=1, seed=42,
        no slippage), computes metrics, and returns a ComparisonTable.

        Args:
            variants: List of variant specifications.
            metrics: Metric names to compute. Defaults to
                ["sharpe", "cagr", "max_drawdown"].
            tax_regime: Tax regime forwarded to each simulate() call.
                Defaults to ``"italian"``.
            tax_params: Regime-specific tax parameters forwarded to each
                simulate() call. Defaults to ``{}``.
            monthly_contribution: Monthly contribution forwarded to each
                simulate() call. When ``None``, the BacktestConfig default
                (500 EUR) is used.

        Returns:
            ComparisonTable with one VariantResult per variant.

        Raises:
            ValueError: If any variant dict is missing "strategy".
            ValueError: If variants list is empty.
        """
        if not variants:
            raise ValueError("variants list must not be empty.")
        metric_names = metrics or ["sharpe", "cagr", "max_drawdown"]
        variant_results: list[VariantResult] = []
        for v in variants:
            if "strategy" not in v:
                raise ValueError("Each variant must have a 'strategy' key.")
            strategy = v["strategy"]
            params: dict[str, Any] = v.get("params", {})
            label: str = v.get(
                "label",
                self._auto_label(strategy, params),
            )
            # Fail fast on unknown strategy
            self._resolve_strategy(strategy, params)
            sim = self.simulate(
                strategy,
                params,
                tax_regime=tax_regime,
                tax_params=tax_params,
                monthly_contribution=monthly_contribution,
            )
            m = self.compute_metrics(sim, metric_names)
            variant_results.append(
                VariantResult(
                    label=label,
                    strategy=strategy,
                    params=params,
                    final_value=float(sim.final_value),
                    metrics=m,
                )
            )
        return ComparisonTable(
            variants=variant_results,
            metric_names=metric_names,
        )

    def sweep(
        self,
        strategy: str,
        grid: dict[str, list[Any]],
        *,
        metrics: list[str] | None = None,
        base_params: dict[str, Any] | None = None,
        tax_regime: str = "italian",
        tax_params: dict[str, Any] | None = None,
        monthly_contribution: Decimal | dict[str, Any] | None = None,
    ) -> SweepResult:
        """Run a parameter grid sweep using quick-test simulation.

        Computes the Cartesian product of all grid values, merges each
        combination with base_params, runs simulate() for each, and
        returns a SweepResult.

        Args:
            strategy: Strategy name.
            grid: Parameter name → list of values to sweep.
            metrics: Metric names to compute. Defaults to
                ["sharpe", "cagr", "max_drawdown"].
            base_params: Fixed params merged with each grid combination.
            tax_regime: Tax regime forwarded to each simulate() call.
                Defaults to ``"italian"``.
            tax_params: Regime-specific tax parameters forwarded to each
                simulate() call. Defaults to ``{}``.
            monthly_contribution: Monthly contribution forwarded to each
                simulate() call. When ``None``, the BacktestConfig default
                (500 EUR) is used.

        Returns:
            SweepResult with one VariantResult per grid point.

        Raises:
            ValueError: If grid is empty or any param has empty values.
        """
        if not grid:
            raise ValueError("grid must not be empty.")
        for key, vals in grid.items():
            if not vals:
                raise ValueError(f"Grid parameter '{key}' has an empty values list.")
        metric_names = metrics or ["sharpe", "cagr", "max_drawdown"]
        keys = list(grid.keys())
        values = [grid[k] for k in keys]
        variant_results: list[VariantResult] = []
        for combo in itertools.product(*values):
            combo_dict = dict(zip(keys, combo, strict=True))
            merged = {**(base_params or {}), **combo_dict}
            label = self._auto_label(strategy, merged)
            sim = self.simulate(
                strategy,
                merged,
                tax_regime=tax_regime,
                tax_params=tax_params,
                monthly_contribution=monthly_contribution,
            )
            m = self.compute_metrics(sim, metric_names)
            variant_results.append(
                VariantResult(
                    label=label,
                    strategy=strategy,
                    params=merged,
                    final_value=float(sim.final_value),
                    metrics=m,
                )
            )
        return SweepResult(
            strategy=strategy,
            param_grid=grid,
            results=variant_results,
            metric_names=metric_names,
        )

    # ── OOS validation ──────────────────────────────────────

    def _simulate_window(
        self,
        strategy: str,
        params: dict[str, Any] | None,
        start: date,
        end: date,
    ) -> IterationResult:
        """Run a quick-test simulation over a date sub-range.

        Creates a temporary BacktestConfig with the given date range,
        slices price data, and runs a single deterministic iteration.
        """
        config = BacktestConfig(
            strategy=strategy,
            strategy_params=params or {},
            start_date=start,
            end_date=end,
            monte_carlo_iterations=1,
            slippage_days=(0, 0),
        )
        strategy_instance = self._resolve_strategy(strategy, params)
        signal_registry = self._signal_registry()

        window_prices = {
            ticker: series.slice(start, end)
            for ticker, series in self._ticker_price_data.items()
        }

        if any(len(s.bars) == 0 for s in window_prices.values()):
            raise ValueError(f"No price data in window [{start}, {end}]")

        simulator = BacktestSimulator(
            config,
            self._settings,
            window_prices,
            signal_registry,
            strategy_instance,
            rng_seed=42,
        )
        return simulator.run_iteration(0)

    def validate_oos(
        self,
        strategy: str,
        params: dict[str, Any] | None = None,
        *,
        split_date: date | None = None,
        split_ratio: float = 0.7,
        metrics: list[str] | None = None,
    ) -> OOSResult:
        """Temporal holdout validation — split price data at a date.

        Runs the strategy with identical params on both in-sample and
        out-of-sample periods. Compares metrics to detect overfitting.
        """
        metric_names = metrics or ["sharpe", "cagr", "max_drawdown"]

        if split_date is None:
            if not (0.0 < split_ratio < 1.0):
                raise ValueError(
                    f"split_ratio must be in (0.0, 1.0), got {split_ratio}"
                )
            total_days = (self._data_end - self._data_start).days
            split_date = self._data_start + timedelta(
                days=int(total_days * split_ratio)
            )

        if split_date <= self._data_start or split_date >= self._data_end:
            raise ValueError(
                f"split_date ({split_date}) must be between "
                f"data_start ({self._data_start}) and data_end ({self._data_end})"
            )

        is_result = self._simulate_window(
            strategy, params, self._data_start, split_date - timedelta(days=1)
        )
        oos_result = self._simulate_window(strategy, params, split_date, self._data_end)

        is_metrics = self.compute_metrics(is_result, metric_names)
        oos_metrics = self.compute_metrics(oos_result, metric_names)

        primary = metric_names[0]
        is_primary = is_metrics.get(primary, 0.0)
        oos_primary = oos_metrics.get(primary, 0.0)
        if is_primary == 0.0:
            degradation_ratio = float("nan")
        else:
            degradation_ratio = oos_primary / is_primary

        return OOSResult(
            split_date=split_date,
            in_sample_metrics=is_metrics,
            out_of_sample_metrics=oos_metrics,
            in_sample_final_value=float(is_result.final_value),
            out_of_sample_final_value=float(oos_result.final_value),
            degradation_ratio=degradation_ratio,
        )

    def walk_forward(
        self,
        strategy: str,
        params: dict[str, Any] | None = None,
        *,
        window_years: int = 10,
        step_years: int = 5,
        min_oos_days: int = 90,
        metrics: list[str] | None = None,
    ) -> WalkForwardResult:
        """Expanding walk-forward validation with fixed parameters.

        Creates expanding IS windows with fixed OOS periods. Tests whether
        the strategy performs consistently across different market decades.
        """
        import statistics

        metric_names = metrics or ["sharpe", "cagr", "max_drawdown"]
        primary = metric_names[0]

        windows: list[tuple[date, date, date, date]] = []
        is_end_date = self._data_start + timedelta(days=window_years * 365)
        while True:
            oos_end_date = is_end_date + timedelta(days=step_years * 365)
            if oos_end_date > self._data_end:
                oos_end_date = self._data_end
            if is_end_date >= self._data_end:
                break
            if (oos_end_date - is_end_date).days < min_oos_days:
                break
            windows.append(
                (
                    self._data_start,
                    is_end_date,
                    is_end_date + timedelta(days=1),
                    oos_end_date,
                )
            )
            is_end_date = oos_end_date

        if not windows:
            total_needed = window_years + step_years
            raise ValueError(
                f"Data too short for walk-forward: need ~{total_needed} years, "
                f"have {(self._data_end - self._data_start).days / 365:.1f} years"
            )

        wf_windows: list[WFWindow] = []
        oos_primary_values: list[float] = []
        for idx, (is_start, is_end, oos_start, oos_end) in enumerate(windows):
            is_result = self._simulate_window(strategy, params, is_start, is_end)
            oos_result = self._simulate_window(strategy, params, oos_start, oos_end)
            is_m = self.compute_metrics(is_result, metric_names)
            oos_m = self.compute_metrics(oos_result, metric_names)
            oos_primary_values.append(oos_m.get(primary, 0.0))
            wf_windows.append(
                WFWindow(
                    window_index=idx,
                    is_start=is_start,
                    is_end=is_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                    is_metrics=is_m,
                    oos_metrics=oos_m,
                )
            )

        if len(oos_primary_values) <= 1:
            stability_score = float("nan")
        else:
            std = statistics.stdev(oos_primary_values)
            mean = statistics.mean(oos_primary_values)
            stability_score = float("inf") if std == 0.0 else mean / std

        consistent = sum(1 for v in oos_primary_values if v > 0)

        return WalkForwardResult(
            windows=wf_windows,
            strategy=strategy,
            params=params or {},
            metric_names=metric_names,
            stability_score=stability_score,
            consistent_windows=consistent,
        )

    def evaluate_events(
        self,
        strategy: str,
        params: dict[str, Any] | None = None,
        *,
        calendar: EventCalendar,
        metrics: list[str] | None = None,
    ) -> EventAnalysisResult:
        """Event-based performance evaluation.

        Runs the strategy on the full data period once, then extracts
        per-event performance by measuring equity curve behavior
        during each event window.
        """
        import statistics as _stats

        if len(calendar) == 0:
            raise ValueError("Calendar has no events.")

        metric_names = metrics or ["sharpe", "cagr", "max_drawdown"]

        # Filter events to those overlapping with the data range
        relevant_events = [
            e
            for e in calendar.events
            if e.start <= self._data_end and e.end >= self._data_start
        ]
        if not relevant_events:
            raise ValueError(
                "No events in calendar overlap with data range "
                f"[{self._data_start}, {self._data_end}]"
            )

        # Run ONE full simulation
        result = self.simulate(strategy, params)

        per_event: list[EventMetrics] = []
        for event in relevant_events:
            # Find trading days within the event window
            sub_values = [
                dv for dv in result.daily_values if event.start <= dv.date <= event.end
            ]

            if len(sub_values) < 2:
                event_return = float("nan")
                event_metrics = {m: float("nan") for m in metric_names}
            else:
                start_val = float(sub_values[0].total_value)
                end_val = float(sub_values[-1].total_value)
                if start_val == 0.0:
                    event_return = float("nan")
                else:
                    event_return = (end_val - start_val) / start_val

                sub_result = IterationResult(
                    iteration=0,
                    daily_values=sub_values,
                    trades=[],
                    final_value=sub_values[-1].total_value,
                )
                event_metrics = self.compute_metrics(sub_result, metric_names)

            per_event.append(
                EventMetrics(
                    event_name=event.name,
                    event_start=event.start,
                    event_end=event.end,
                    event_tags=sorted(event.tags),
                    metrics_during_event=event_metrics,
                    event_return=event_return,
                )
            )

        returns = [e.event_return for e in per_event]
        valid_returns = [r for r in returns if not _is_nan(r)]

        if valid_returns:
            mean_event_return = _stats.mean(valid_returns)
        else:
            mean_event_return = float("nan")

        if len(valid_returns) < 2:
            generalization_score = float("nan")
        else:
            min_return = min(valid_returns)
            max_return = max(valid_returns)
            if min_return < 0 < max_return:
                generalization_score = float("nan")
            elif max_return > 0:
                generalization_score = min_return / max_return
            else:
                generalization_score = float("nan")

        return EventAnalysisResult(
            calendar_name=calendar.name,
            strategy=strategy,
            params=params or {},
            metric_names=metric_names,
            per_event=per_event,
            mean_event_return=mean_event_return,
            generalization_score=generalization_score,
        )

    # ── Quantstats ──────────────────────────────────────────

    def quantstats(
        self,
        result: IterationResult | SimulationResult,
        *,
        metrics: list[str] | str | None = None,
    ) -> QuantstatsMetrics:
        """Compute quantstats metrics from a simulation result.

        For extended metrics beyond the core MetricsCalculator,
        see ``quantstats()``.

        Args:
            result: Single iteration or full MC simulation.
            metrics: List of metric names, ``"all"`` for everything,
                or ``None`` for defaults (sharpe, sortino, calmar,
                max_drawdown, cagr, volatility, omega).

        Returns:
            QuantstatsMetrics with float values (single iteration)
            or MetricBand values (MC aggregated to P5/median/P95).
        """
        from pac.backtester.research._quantstats_helpers import (
            _EXTENDED_METRICS,
            _result_to_returns,
        )
        from pac.backtester.research._quantstats_helpers import (
            compute_metrics as _compute_qs_metrics,
        )
        from pac.backtester.research.models import MetricBand

        if metrics == "all":
            metric_names = list(_EXTENDED_METRICS.keys())
        elif isinstance(metrics, list):
            metric_names = metrics
        else:
            metric_names = None  # defaults inside compute_metrics

        if isinstance(result, IterationResult):
            returns = _result_to_returns(result)
            single_values = _compute_qs_metrics(returns, metric_names)
            return QuantstatsMetrics(metrics={k: v for k, v in single_values.items()})

        # SimulationResult — MC aggregation
        import numpy as np

        all_metrics: dict[str, list[float]] = {}
        for iteration in result.iterations:
            returns = _result_to_returns(iteration)
            iter_values = _compute_qs_metrics(returns, metric_names)
            for k, v in iter_values.items():
                all_metrics.setdefault(k, []).append(v)

        aggregated: dict[str, float | MetricBand] = {}
        for k, vals in all_metrics.items():
            arr = np.array(vals)
            p5, median, p95 = np.nanpercentile(arr, [5, 50, 95]).tolist()
            aggregated[k] = MetricBand(p5=p5, median=median, p95=p95)

        return QuantstatsMetrics(metrics=aggregated)

    def quantstats_report(
        self,
        result: IterationResult,
        output: str | Path,
        *,
        benchmark: IterationResult | None = None,
        title: str = "Quantstats Report",
    ) -> Path:
        """Generate a full HTML tearsheet and save to disk.

        Args:
            result: Single iteration result.
            output: Output file path (relative paths resolved against CWD).
            benchmark: Optional benchmark result for comparison.
            title: Report title.

        Returns:
            Absolute path to the generated HTML file.
        """
        from pac.backtester.research._quantstats_helpers import (
            _result_to_returns,
            generate_html_report,
        )

        returns = _result_to_returns(result)
        bench_returns = _result_to_returns(benchmark) if benchmark else None
        return generate_html_report(
            returns,
            output,
            benchmark_returns=bench_returns,
            title=title,
        )

    def quantstats_plot(
        self,
        result: IterationResult,
        kind: str,
        *,
        benchmark: IterationResult | None = None,
    ) -> Any:  # matplotlib.figure.Figure
        """Generate a single quantstats plot as a matplotlib Figure.

        Args:
            result: Single iteration result.
            kind: Plot type — ``"returns"``, ``"monthly_heatmap"``,
                ``"drawdown"``, ``"rolling_sharpe"``,
                ``"rolling_sortino"``, ``"rolling_volatility"``,
                ``"histogram"``, ``"daily_returns"``,
                ``"distribution"``, ``"drawdowns_periods"``.
            benchmark: Optional benchmark for overlay.

        Returns:
            matplotlib.figure.Figure.

        Raises:
            ValueError: If kind is not a supported plot type.
        """
        from pac.backtester.research._quantstats_helpers import (
            _result_to_returns,
            generate_plot,
        )

        returns = _result_to_returns(result)
        bench_returns = _result_to_returns(benchmark) if benchmark else None
        return generate_plot(returns, kind, benchmark_returns=bench_returns)

    def quantstats_rolling(
        self,
        result: IterationResult,
        metric: str = "sharpe",
        *,
        window: int = 252,
    ) -> list[tuple[date, float]]:
        """Compute a rolling metric over the equity curve.

        Args:
            result: Single iteration result.
            metric: Rolling metric name — ``"sharpe"``, ``"sortino"``,
                ``"volatility"``.
            window: Rolling window in trading days (default 252 = ~1 year).

        Returns:
            List of (date, value) tuples for the rolling metric.

        Raises:
            ValueError: If metric is not a supported rolling metric.
        """
        from pac.backtester.research._quantstats_helpers import (
            _result_to_returns,
            compute_rolling,
        )

        returns = _result_to_returns(result)
        return compute_rolling(returns, metric, window=window)

    def quantstats_save_plots(
        self,
        result: IterationResult,
        output_dir: str | Path,
        *,
        kinds: list[str] | None = None,
        fmt: str = "png",
        benchmark: IterationResult | None = None,
    ) -> list[Path]:
        """Batch-save quantstats plots to a directory.

        Args:
            result: Single iteration result.
            output_dir: Directory to save plots in (created if missing).
            kinds: Which plots to generate. Defaults to the 6 most
                useful standard plots.
            fmt: Image format (``"png"``, ``"svg"``, ``"pdf"``). Named
                ``fmt`` to avoid shadowing the Python built-in ``format()``.
            benchmark: Optional benchmark for overlay.

        Returns:
            List of paths to saved plot files.
        """
        import matplotlib.pyplot as plt

        default_kinds = [
            "returns",
            "monthly_heatmap",
            "drawdown",
            "rolling_sharpe",
            "histogram",
            "distribution",
        ]
        selected = kinds if kinds is not None else default_kinds
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        saved: list[Path] = []
        for kind in selected:
            fig = self.quantstats_plot(result, kind, benchmark=benchmark)
            filepath = out / f"{kind}.{fmt}"
            fig.savefig(str(filepath))
            plt.close(fig)
            saved.append(filepath)

        return saved

    # ── Internal helpers ────────────────────────────────────

    def _signal_registry(self) -> SignalRegistry:
        """Lazy-build and cache the signal registry."""
        if self._rules is None:
            rule_classes = discover_rules()
            registry = SignalRegistry()
            for rule_cls in rule_classes.values():
                registry.register(rule_cls)
            self._rules = registry
        return self._rules

    def _resolve_strategy(
        self,
        strategy_name: str,
        params: dict[str, Any] | None,
    ) -> BacktestStrategy[Any]:
        """Discover (cached), validate, and instantiate a strategy."""
        if self._strategies is None:
            self._strategies = discover_strategies()
        available = self._strategies
        if strategy_name not in available:
            raise ValueError(
                f"Unknown strategy '{strategy_name}'. "
                f"Available: {', '.join(sorted(available))}"
            )
        strategy_cls = available[strategy_name]
        validated_params = strategy_cls.params_model.model_validate(params or {})
        return strategy_cls(validated_params)
