"""Crisis indicator pack — wraps the 6 production crisis indicators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pac.models.market_data import PriceSeries

if TYPE_CHECKING:
    from pac.backtester.research.indicators import IndicatorRegistry, IndicatorResult


@dataclass(frozen=True)
class CrisisIndicatorDef:
    """Wraps a function from pac.rules.builtin._indicators."""

    name: str
    lookback_days: int
    required_assets: list[str]
    _compute_fn: Callable[..., Any]
    _extract_fn: Callable[[Any], IndicatorResult]
    _param_map: dict[str, str]
    """Maps asset IDs to function parameter names.
    e.g., {"stocks": "equity_series", "gold": "gold_series"}."""
    _default_kwargs: dict[str, object] = field(default_factory=dict)

    def compute(
        self,
        price_data: dict[str, PriceSeries],
        **kwargs: object,
    ) -> IndicatorResult:
        merged = {**self._default_kwargs, **kwargs}
        resolved = self._resolve_args(price_data, merged)
        raw = self._compute_fn(**resolved)
        return self._extract_fn(raw)

    def _resolve_args(
        self,
        price_data: dict[str, PriceSeries],
        kwargs: dict[str, object],
    ) -> dict[str, object]:
        """Map required_assets to the compute function's parameter names."""
        args: dict[str, object] = {}
        for asset_id, param_name in self._param_map.items():
            args[param_name] = price_data[asset_id]
        args.update(kwargs)
        return args


class CrisisPack:
    """Indicator pack wrapping the 6 production crisis detection indicators.

    Delegates to pac.rules.builtin._indicators — no duplicated math.
    """

    @property
    def name(self) -> str:
        return "crisis"

    @property
    def description(self) -> str:
        return (
            "6 crisis detection indicators from production: "
            "drawdown, divergence, volatility, correlation, "
            "relative_strength, death_cross"
        )

    def register(self, registry: IndicatorRegistry) -> None:
        from pac.rules.builtin._indicators import (
            compute_correlation,
            compute_death_cross,
            compute_divergence,
            compute_drawdown,
            compute_relative_strength,
            compute_volatility_regime,
        )

        crisis_defs: list[CrisisIndicatorDef] = [
            CrisisIndicatorDef(
                name="drawdown",
                lookback_days=400,
                required_assets=["stocks"],
                _compute_fn=compute_drawdown,
                _extract_fn=lambda r: r.drawdown_pct,
                _param_map={"stocks": "equity_series"},
                _default_kwargs={"lookback_bars": 252},
            ),
            CrisisIndicatorDef(
                name="divergence",
                lookback_days=100,
                required_assets=["gold", "stocks"],
                _compute_fn=compute_divergence,
                _extract_fn=lambda r: r.divergence,
                _param_map={
                    "gold": "gold_series",
                    "stocks": "equity_series",
                },
                _default_kwargs={"lookback_bars": 40},
            ),
            CrisisIndicatorDef(
                name="volatility",
                lookback_days=120,
                required_assets=["stocks"],
                _compute_fn=compute_volatility_regime,
                _extract_fn=lambda r: r.vol_ratio,
                _param_map={"stocks": "equity_series"},
                _default_kwargs={"short_window": 20, "long_window": 60},
            ),
            CrisisIndicatorDef(
                name="correlation",
                lookback_days=120,
                required_assets=["bonds", "stocks"],
                _compute_fn=compute_correlation,
                _extract_fn=lambda r: r.correlation,
                _param_map={
                    "bonds": "bond_series",
                    "stocks": "equity_series",
                },
                _default_kwargs={"window": 60},
            ),
            CrisisIndicatorDef(
                name="relative_strength",
                lookback_days=200,
                required_assets=["gold", "stocks"],
                _compute_fn=compute_relative_strength,
                _extract_fn=lambda r: r.breakout_pct,
                _param_map={
                    "gold": "gold_series",
                    "stocks": "equity_series",
                },
                _default_kwargs={"ma_window": 120},
            ),
            CrisisIndicatorDef(
                name="death_cross",
                lookback_days=300,
                required_assets=["stocks"],
                _compute_fn=compute_death_cross,
                _extract_fn=lambda r: r.bearish_regime,
                _param_map={"stocks": "equity_series"},
                _default_kwargs={"short_window": 50, "long_window": 200},
            ),
        ]
        for defn in crisis_defs:
            registry.register_def(defn)
