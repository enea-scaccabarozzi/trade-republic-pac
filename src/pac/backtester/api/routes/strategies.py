"""Route for listing available backtest strategies."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from pac.backtester.api.models import StrategiesResponse, StrategyInfo
from pac.backtester.strategies.discovery import discover_strategies

router = APIRouter()


@router.get("/strategies", response_model=StrategiesResponse)
def list_strategies() -> StrategiesResponse:
    """List all discovered backtest strategies with JSON Schema for params."""
    available: dict[str, type[Any]] = discover_strategies()
    infos: list[StrategyInfo] = []
    for name in sorted(available):
        cls = available[name]
        doc = (cls.__doc__ or "").strip()
        first_line = doc.splitlines()[0] if doc else ""
        schema: dict[str, Any] = cls.params_model.model_json_schema()
        infos.append(
            StrategyInfo(
                name=name,
                description=first_line,
                params_schema=schema,
            ),
        )
    return StrategiesResponse(strategies=infos)
