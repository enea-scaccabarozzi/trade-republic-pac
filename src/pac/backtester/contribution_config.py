from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

__all__ = ["ContributionConfig"]


class ContributionConfig(BaseModel, frozen=True):
    """Configuration for a stochastic monthly contribution distribution.

    Attributes:
        min: Minimum contribution amount (inclusive, must be >= 0).
        max: Maximum contribution amount (inclusive, must be >= min).
        distribution: Distribution type — ``"uniform"`` (default) or ``"normal"``.
        std: Optional standard deviation for the normal distribution.
            Defaults to ``(max - min) / 4`` when omitted.
    """

    min: Decimal = Field(ge=0)
    max: Decimal = Field(ge=0)
    distribution: str = "uniform"
    std: Decimal | None = None

    @model_validator(mode="after")
    def _validate_min_lte_max(self) -> ContributionConfig:
        if self.min > self.max:
            raise ValueError(
                f"ContributionConfig.min ({self.min}) must be <= max ({self.max})"
            )
        return self
