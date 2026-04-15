"""Indicator registry — unified, empty-by-default indicator system.

Supports extensible indicator packs and custom indicator functions.
Provides compute() (single date) and series() (date range) primitives.
"""

from __future__ import annotations

__all__ = [
    "CompositeResult",
    "IndicatorDef",
    "IndicatorRegistry",
    "IndicatorResult",
    "threshold",
]

import operator
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pac.models.market_data import PriceSeries

if TYPE_CHECKING:
    import numpy as np

    IndicatorResult = float | bool | np.ndarray | tuple[np.ndarray, ...]
else:
    # Runtime placeholder — avoids importing numpy at module level.
    IndicatorResult = float | bool | object


@runtime_checkable
class IndicatorDef(Protocol):
    """Protocol for a registered indicator definition."""

    @property
    def name(self) -> str: ...

    @property
    def lookback_days(self) -> int:
        """Calendar days of price data needed before the target date."""
        ...

    @property
    def required_assets(self) -> list[str]:
        """Asset IDs this indicator needs (e.g., ["stocks"])."""
        ...

    def compute(
        self,
        price_data: dict[str, PriceSeries],
        **kwargs: object,
    ) -> IndicatorResult:
        """Compute the indicator value from sliced price data.

        Args:
            price_data: Mapping of asset_id -> PriceSeries, already sliced
                        to [target_date - lookback_days, target_date].
            **kwargs: Indicator-specific parameters (e.g., period=14).

        Returns:
            Scalar float, boolean, numpy array, or tuple of arrays.
        """
        ...


@dataclass(frozen=True)
class CustomIndicatorDef:
    """Wraps a user-defined indicator function."""

    name: str
    _fn: Callable[..., IndicatorResult]
    lookback_days: int
    required_assets: list[str]

    def compute(
        self,
        price_data: dict[str, PriceSeries],
        **kwargs: object,
    ) -> IndicatorResult:
        if len(self.required_assets) == 1:
            series = price_data[self.required_assets[0]]
            return self._fn(series, **kwargs)
        return self._fn(price_data, **kwargs)


@dataclass(frozen=True)
class CompositeResult:
    """Result of composite N-of-M voting for a single date."""

    date: date
    active: bool
    active_count: int
    total: int
    min_active: int
    votes: dict[str, bool]
    values: dict[str, IndicatorResult | None]


def threshold(op: str, value: float) -> Callable[[IndicatorResult], bool]:
    """Build a threshold function for composite_series().

    Args:
        op: Comparison operator — one of "<", "<=", ">", ">=".
        value: Numeric threshold.

    Returns:
        A callable (IndicatorResult) -> bool.

    Raises:
        ValueError: If op is not a supported operator.

    Example:
        composite_series(
            indicators=["rsi", "drawdown"],
            thresholds={
                "rsi": threshold("<", 30),
                "drawdown": threshold("<", -0.12),
            },
            ...
        )
    """
    ops: dict[str, Callable[..., bool]] = {
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
    }
    if op not in ops:
        raise ValueError(f"Unsupported operator {op!r}. Use one of: <, <=, >, >=")
    op_fn = ops[op]

    def _threshold(result: IndicatorResult) -> bool:
        return bool(op_fn(result, value))

    return _threshold


class IndicatorRegistry:
    """Unified indicator registry — starts empty.

    Load indicators via:
        register_pack("tulipy")     — 104 compiled C TA indicators
        register_pack("crisis")     — 6 crisis indicators from production
        register(name, fn, ...)     — custom indicator function

    Compute indicators via:
        compute(name, target_date, asset, **kwargs)    — single date
        series(name, start, end, asset, **kwargs)      — date range
        list()                                          — list registered names
    """

    def __init__(self, price_data: dict[str, PriceSeries]) -> None:
        self._price_data = price_data
        self._indicators: dict[str, IndicatorDef] = {}

    def register_pack(self, pack_name: str) -> None:
        """Load a named indicator pack via discovery.

        Scans packs/ subdirectories for classes implementing IndicatorPack,
        matches by name, and calls pack.register(self).

        Raises:
            ValueError: If pack_name is not found among discovered packs.
        """
        from pac.backtester.research.packs import discover_packs

        packs = discover_packs()
        if pack_name not in packs:
            available = sorted(packs.keys())
            raise ValueError(
                f"Unknown indicator pack: {pack_name!r}. " f"Available: {available}"
            )
        packs[pack_name].register(self)

    def register(
        self,
        name: str,
        fn: Callable[..., IndicatorResult],
        *,
        asset: str = "stocks",
        assets: list[str] | None = None,
        lookback_days: int = 252,
    ) -> None:
        """Register a custom indicator function.

        Args:
            name: Unique indicator name.
            fn: Indicator function.
                Single-asset: (PriceSeries, **kwargs) -> IndicatorResult
                Multi-asset: (dict[str, PriceSeries], **kwargs) -> IndicatorResult
            asset: Single required asset ID (ignored if assets is provided).
            assets: List of required asset IDs (for multi-asset indicators).
            lookback_days: Calendar days of price history needed.

        Raises:
            ValueError: If name is already registered.
        """
        if name in self._indicators:
            raise ValueError(f"Indicator {name!r} is already registered")
        required = assets if assets is not None else [asset]
        self._indicators[name] = CustomIndicatorDef(
            name=name,
            _fn=fn,
            lookback_days=lookback_days,
            required_assets=required,
        )

    def register_def(self, indicator: IndicatorDef) -> None:
        """Register a pre-built IndicatorDef (used by packs internally).

        Raises:
            ValueError: If indicator.name is already registered.
        """
        if indicator.name in self._indicators:
            raise ValueError(f"Indicator {indicator.name!r} is already registered")
        self._indicators[indicator.name] = indicator

    def compute(
        self,
        name: str,
        target_date: date,
        *,
        asset: str | None = None,
        **kwargs: object,
    ) -> IndicatorResult:
        """Compute a registered indicator for a single date.

        Args:
            name: Registered indicator name.
            target_date: The date to compute the indicator for.
            asset: Override the default asset (single-asset indicators only).
            **kwargs: Indicator-specific parameters.

        Returns:
            IndicatorResult (float, bool, ndarray, or tuple of ndarrays).

        Raises:
            KeyError: If name is not registered.
            ValueError: If asset override used on a multi-asset indicator.
        """
        indicator = self._indicators[name]
        sliced = self._slice_price_data(indicator, target_date, asset)
        return indicator.compute(sliced, **kwargs)

    def series(
        self,
        name: str,
        start: date,
        end: date,
        *,
        asset: str | None = None,
        **kwargs: object,
    ) -> list[tuple[date, IndicatorResult]]:
        """Compute indicator for every trading day in [start, end].

        This is the missing primitive — replaces the manual sliding-window
        loop reimplemented 10+ times during Task 010.

        Complexity: O(N x M) where N = trading days in range and
        M = lookback_days per indicator. Each day re-slices the full
        price data. A vectorized tulipy fast-path is deferred.

        Args:
            name: Registered indicator name.
            start: Start date (inclusive).
            end: End date (inclusive).
            asset: Override the default asset (single-asset indicators only).
            **kwargs: Indicator-specific parameters.

        Returns:
            List of (date, result) pairs for each trading day in range.
            Days where computation fails (insufficient data) are skipped.

        Raises:
            ValueError: If asset override used on a multi-asset indicator.
        """
        indicator = self._indicators[name]
        # Validate asset override early (before looping)
        if asset is not None and len(indicator.required_assets) > 1:
            raise ValueError(
                f"Cannot use asset override on multi-asset indicator "
                f"{indicator.name!r} (requires {indicator.required_assets}). "
                f"asset override is only valid for single-asset indicators."
            )

        primary_asset = asset or indicator.required_assets[0]
        full_series = self._price_data.get(primary_asset)
        if full_series is None:
            return []

        trading_days = [
            bar.date for bar in full_series.bars if start <= bar.date <= end
        ]

        results: list[tuple[date, IndicatorResult]] = []
        for day in trading_days:
            try:
                sliced = self._slice_price_data(indicator, day, asset)
                value = indicator.compute(sliced, **kwargs)
                results.append((day, value))
            except (ValueError, KeyError):
                continue
        return results

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

        Args:
            indicators: List of indicator names or (name, kwargs) tuples.
            min_active: The N in N-of-M — how many must vote True.
            start: Start date (inclusive).
            end: End date (inclusive).
            thresholds: Mapping of indicator name to a callable that
                converts a numeric IndicatorResult to bool. Required for
                numeric indicators; boolean indicators work without.

        Returns:
            List of CompositeResult for every trading day in range.

        Raises:
            KeyError: If any indicator name is not registered.
            ValueError: If min_active is out of range or a numeric
                indicator has no threshold entry.
        """
        if not indicators:
            return []

        thresholds = thresholds or {}

        # Parse indicator specs
        parsed: list[tuple[str, dict[str, object]]] = []
        for spec in indicators:
            if isinstance(spec, str):
                parsed.append((spec, {}))
            else:
                parsed.append(spec)

        # Validate all names are registered
        for name, _ in parsed:
            if name not in self._indicators:
                raise KeyError(f"Indicator {name!r} is not registered")

        # Validate min_active
        if min_active < 1 or min_active > len(parsed):
            raise ValueError(
                f"min_active must be between 1 and {len(parsed)}, " f"got {min_active}"
            )

        # Determine trading days from the first indicator's primary asset
        first_indicator = self._indicators[parsed[0][0]]
        primary_asset = first_indicator.required_assets[0]
        full_series = self._price_data.get(primary_asset)
        if full_series is None:
            return []

        trading_days = [
            bar.date for bar in full_series.bars if start <= bar.date <= end
        ]

        results: list[CompositeResult] = []
        for day in trading_days:
            votes: dict[str, bool] = {}
            values: dict[str, IndicatorResult | None] = {}

            for name, kwargs in parsed:
                try:
                    indicator = self._indicators[name]
                    sliced = self._slice_price_data(indicator, day, None)
                    raw = indicator.compute(sliced, **kwargs)
                except (ValueError, KeyError):
                    votes[name] = False
                    values[name] = None
                    continue

                values[name] = raw

                # Convert to boolean vote
                # Check bool BEFORE float — bool is a subclass of float
                if isinstance(raw, bool):
                    votes[name] = raw
                elif name in thresholds:
                    votes[name] = thresholds[name](raw)
                else:
                    raise ValueError(
                        f"Indicator {name!r} returns a numeric value. "
                        f"Provide a threshold function in "
                        f"thresholds={{'{name}': lambda v: v < 30}}"
                    )

            active_count = sum(votes.values())
            results.append(
                CompositeResult(
                    date=day,
                    active=active_count >= min_active,
                    active_count=active_count,
                    total=len(parsed),
                    min_active=min_active,
                    votes=votes,
                    values=values,
                )
            )

        return results

    def list(self) -> list[str]:
        """List all registered indicator names, sorted alphabetically."""
        return sorted(self._indicators.keys())

    def get(self, name: str) -> IndicatorDef:
        """Get an indicator definition by name.

        Raises:
            KeyError: If name is not registered.
        """
        return self._indicators[name]

    def _slice_price_data(
        self,
        indicator: IndicatorDef,
        target_date: date,
        asset_override: str | None,
    ) -> dict[str, PriceSeries]:
        """Slice price data to [target_date - lookback, target_date].

        Raises:
            ValueError: If asset_override is used on a multi-asset indicator.
        """
        if asset_override is not None and len(indicator.required_assets) > 1:
            raise ValueError(
                f"Cannot use asset override on multi-asset indicator "
                f"{indicator.name!r} (requires {indicator.required_assets}). "
                f"asset override is only valid for single-asset indicators."
            )

        start = target_date - timedelta(days=indicator.lookback_days)
        assets = [asset_override] if asset_override else indicator.required_assets
        result: dict[str, PriceSeries] = {}
        for i, asset_id in enumerate(assets):
            full = self._price_data.get(asset_id)
            if full is None:
                raise KeyError(f"No price data for asset {asset_id!r}")
            # Use original asset name as key so param_map resolution works
            key = indicator.required_assets[i] if asset_override else asset_id
            result[key] = full.slice(start, target_date)
        return result
