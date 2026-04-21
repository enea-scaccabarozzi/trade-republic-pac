from __future__ import annotations

import random
from abc import ABC, abstractmethod
from decimal import Decimal

from pac.backtester.contribution_config import ContributionConfig

__all__ = [
    "ContributionConfig",
    "ContributionDistribution",
    "FixedContribution",
    "NormalContribution",
    "UniformContribution",
    "resolve_contribution",
]


class ContributionDistribution(ABC):
    """Abstract base for monthly contribution amount distributions.

    Implementations are stateless — no ``reset()`` is needed between
    Monte Carlo iterations, unlike ``TaxRegime`` which carries forward state.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this distribution."""
        ...

    @abstractmethod
    def sample(self, rng: random.Random) -> Decimal:
        """Draw a contribution amount from the distribution.

        Args:
            rng: Seeded random number generator provided by the simulator.
                 Using the injected RNG ensures reproducibility.

        Returns:
            A non-negative ``Decimal`` representing the contribution amount
            for one PAC execution.
        """
        ...


class FixedContribution(ContributionDistribution):
    """Contribution distribution that always returns the same fixed amount.

    Use this to model deterministic monthly contributions — the default
    behaviour before stochastic contributions were introduced.
    """

    def __init__(self, amount: Decimal) -> None:
        self._amount = amount

    @property
    def name(self) -> str:
        return "fixed"

    def sample(self, rng: random.Random) -> Decimal:
        """Return the fixed amount regardless of the RNG state.

        Args:
            rng: Ignored — this distribution is deterministic.

        Returns:
            The fixed contribution amount supplied at construction.
        """
        return self._amount


class UniformContribution(ContributionDistribution):
    """Contribution distribution uniform over [min_amount, max_amount].

    Each PAC execution samples independently, producing equal probability
    for any value in the range. Useful for modelling variable income where
    no particular value is more likely than another.
    """

    def __init__(self, min_amount: Decimal, max_amount: Decimal) -> None:
        self._min = min_amount
        self._max = max_amount

    @property
    def name(self) -> str:
        return "uniform"

    def sample(self, rng: random.Random) -> Decimal:
        """Sample a contribution uniformly from [min_amount, max_amount].

        Args:
            rng: Seeded random number generator.

        Returns:
            A ``Decimal`` in ``[min_amount, max_amount]``, quantized to
            2 decimal places.
        """
        raw = self._min + (self._max - self._min) * Decimal(str(rng.random()))
        return raw.quantize(Decimal("0.01"))


class NormalContribution(ContributionDistribution):
    """Truncated normal contribution distribution clipped to [min_amount, max_amount].

    Models variable income that tends towards a central value (e.g. regular
    salary ± bonus). Values outside ``[min_amount, max_amount]`` are clipped,
    producing a truncated normal rather than a true normal.

    Mean is set to ``(min + max) / 2``. Standard deviation defaults to
    ``(max - min) / 4`` so that roughly 95% of unclipped draws fall within
    the ``[min, max]`` range.
    """

    def __init__(
        self,
        min_amount: Decimal,
        max_amount: Decimal,
        std: Decimal | None = None,
    ) -> None:
        self._min = min_amount
        self._max = max_amount
        self._mean = (min_amount + max_amount) / Decimal("2")
        self._std = std if std is not None else (max_amount - min_amount) / Decimal("4")

    @property
    def name(self) -> str:
        return "normal"

    def sample(self, rng: random.Random) -> Decimal:
        """Sample from a truncated normal distribution.

        Draws from ``gauss(mean, std)`` and clips the result to
        ``[min_amount, max_amount]`` before quantizing to 2 decimal places.

        Args:
            rng: Seeded random number generator.

        Returns:
            A ``Decimal`` in ``[min_amount, max_amount]``, quantized to
            2 decimal places.
        """
        raw = Decimal(str(rng.gauss(float(self._mean), float(self._std))))
        clipped = max(self._min, min(self._max, raw))
        return clipped.quantize(Decimal("0.01"))


def resolve_contribution(
    config: Decimal | ContributionConfig,
) -> ContributionDistribution:
    """Resolve a contribution config to a concrete distribution instance.

    Args:
        config: Either a fixed ``Decimal`` amount or a ``ContributionConfig``
            describing a stochastic distribution.

    Returns:
        A ``ContributionDistribution`` ready to sample from.

    Raises:
        ValueError: If ``config.distribution`` is not a recognised value.
    """
    if isinstance(config, Decimal):
        return FixedContribution(config)

    if config.distribution == "uniform":
        return UniformContribution(config.min, config.max)

    if config.distribution == "normal":
        return NormalContribution(config.min, config.max, std=config.std)

    raise ValueError(
        f"Unknown distribution: {config.distribution!r}. "
        "Expected 'uniform' or 'normal'."
    )
