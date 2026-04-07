from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator


class BacktestConfig(BaseModel, frozen=True):
    """Parameters for a single backtest run."""

    strategy: str = Field(description="Strategy name (registered)")
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date: date
    initial_cash: Decimal = Field(default=Decimal("10000"), ge=0)
    monthly_contribution: Decimal = Field(default=Decimal("500"), ge=0)
    pac_execution_days: list[int] = Field(default=[2, 16])
    settlement_fee: Decimal = Field(default=Decimal("1.00"), ge=0)
    spread_bps: Decimal = Field(default=Decimal("10"), ge=0)
    slippage_days: tuple[int, int] = Field(
        default=(0, 3),
        description="Uniform distribution range (min, max) for human delay in days",
    )
    monte_carlo_iterations: int = Field(default=100, ge=1)
    metrics: list[str] = Field(
        default=["sortino", "calmar", "max_drawdown", "cagr", "sharpe"],
    )
    benchmark: bool = Field(
        default=True,
        description="Compare against passive buy-and-hold",
    )

    @model_validator(mode="after")
    def _check_date_range(self) -> BacktestConfig:
        if self.start_date >= self.end_date:
            msg = (
                f"start_date ({self.start_date}) must be"
                f" before end_date ({self.end_date})"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_slippage_range(self) -> BacktestConfig:
        lo, hi = self.slippage_days
        if lo < 0 or hi < lo:
            msg = (
                "slippage_days must be (min, max) with"
                f" 0 <= min <= max, got ({lo}, {hi})"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_pac_days(self) -> BacktestConfig:
        for d in self.pac_execution_days:
            if not 1 <= d <= 28:
                msg = f"PAC execution day must be 1-28, got {d}"
                raise ValueError(msg)
        return self
