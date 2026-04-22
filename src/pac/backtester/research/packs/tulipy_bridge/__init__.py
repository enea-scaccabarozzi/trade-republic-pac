"""Tulipy bridge pack — exposes 104 compiled C TA indicators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pac.models.market_data import PriceSeries

if TYPE_CHECKING:
    import numpy as np

    from pac.backtester.research.indicators import IndicatorRegistry, IndicatorResult


@dataclass(frozen=True)
class TulipyIndicatorDef:
    """Wraps a tulipy indicator function with PriceSeries<->numpy bridging."""

    name: str
    full_name: str
    inputs: tuple[str, ...]
    options: tuple[str, ...]
    outputs: tuple[str, ...]
    _ti_func: object
    lookback_days: int = 300
    required_assets: list[str] = field(default_factory=lambda: ["stocks"])

    def compute(
        self,
        price_data: dict[str, PriceSeries],
        **kwargs: object,
    ) -> IndicatorResult:
        """Convert PriceSeries -> numpy arrays, call tulipy, return result."""
        series = price_data[self.required_assets[0]]
        arrays = self._extract_inputs(series)

        if self.options:
            provided = [kwargs.get(opt) for opt in self.options]
            all_provided = all(v is not None for v in provided)
            none_provided = all(v is None for v in provided)
            if not (all_provided or none_provided):
                given = [
                    opt
                    for opt, v in zip(self.options, provided, strict=True)
                    if v is not None
                ]
                missing = [
                    opt
                    for opt, v in zip(self.options, provided, strict=True)
                    if v is None
                ]
                raise ValueError(
                    f"Tulipy indicator {self.name!r}: provide all options "
                    f"or none. Got {given}, missing {missing}."
                )
            if all_provided:
                result = self._ti_func(*arrays, *provided)  # type: ignore[operator]
            else:
                result = self._ti_func(*arrays)  # type: ignore[operator]
        else:
            result = self._ti_func(*arrays)  # type: ignore[operator]

        if isinstance(result, tuple):
            return result
        return result  # type: ignore[no-any-return]

    def _extract_inputs(self, series: PriceSeries) -> list[np.ndarray]:
        """Map tulipy input names to PriceSeries OHLCV fields."""
        import numpy as np

        mapping: dict[str, str] = {
            "real": "close",
            "close": "close",
            "high": "high",
            "low": "low",
            "open": "open",
            "volume": "volume",
        }
        return [
            np.array(
                [float(getattr(bar, mapping[inp])) for bar in series.bars],
                dtype=np.float64,
            )
            for inp in self.inputs
        ]


class TulipyPack:
    """Indicator pack bridging tulipy's 104 compiled TA indicators."""

    @property
    def name(self) -> str:
        return "tulipy"

    @property
    def description(self) -> str:
        return "104 compiled C technical analysis indicators via tulipy"

    def register(self, registry: IndicatorRegistry) -> None:
        """Lazy-import tulipy and register all indicators."""
        try:
            import tulipy as ti
        except ImportError as exc:
            msg = "tulipy is not installed. Install it with: uv sync --group research"
            raise ImportError(msg) from exc

        for attr_name in dir(ti):
            obj = getattr(ti, attr_name)
            if not (hasattr(obj, "inputs") and hasattr(obj, "options")):
                continue
            registry.register_def(
                TulipyIndicatorDef(
                    name=attr_name,
                    full_name=getattr(obj, "full_name", attr_name),
                    inputs=tuple(obj.inputs),
                    options=tuple(obj.options),
                    outputs=tuple(obj.outputs),
                    _ti_func=obj,
                )
            )
