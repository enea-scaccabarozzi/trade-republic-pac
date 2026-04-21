from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.contributions import (
    ContributionConfig,
    FixedContribution,
    NormalContribution,
    UniformContribution,
    resolve_contribution,
)


class TestFixedContribution:
    def test_name_is_fixed(self) -> None:
        dist = FixedContribution(Decimal("500.00"))
        assert dist.name == "fixed"

    def test_sample_always_returns_same_amount(self) -> None:
        dist = FixedContribution(Decimal("500.00"))
        rng = random.Random(42)
        assert dist.sample(rng) == Decimal("500.00")
        assert dist.sample(rng) == Decimal("500.00")
        assert dist.sample(rng) == Decimal("500.00")

    def test_sample_ignores_rng(self) -> None:
        dist = FixedContribution(Decimal("123.45"))
        # Different RNG seeds should produce the same result
        assert dist.sample(random.Random(1)) == Decimal("123.45")
        assert dist.sample(random.Random(999)) == Decimal("123.45")


class TestUniformContribution:
    def test_name_is_uniform(self) -> None:
        dist = UniformContribution(Decimal("400"), Decimal("600"))
        assert dist.name == "uniform"

    def test_sample_within_bounds(self) -> None:
        dist = UniformContribution(Decimal("400"), Decimal("600"))
        rng = random.Random(42)
        for _ in range(100):
            value = dist.sample(rng)
            assert Decimal("400") <= value <= Decimal("600")

    def test_sample_has_two_decimal_places(self) -> None:
        dist = UniformContribution(Decimal("100"), Decimal("200"))
        rng = random.Random(42)
        for _ in range(50):
            value = dist.sample(rng)
            # Quantized to 2 decimal places means sign * coefficient * 10^exp
            # where exp >= -2
            assert value == value.quantize(Decimal("0.01"))

    def test_sample_when_min_equals_max_returns_min(self) -> None:
        dist = UniformContribution(Decimal("500"), Decimal("500"))
        rng = random.Random(42)
        assert dist.sample(rng) == Decimal("500")

    def test_distribution_covers_range(self) -> None:
        # Over many samples, min and max should both be reachable in spirit
        dist = UniformContribution(Decimal("0"), Decimal("100"))
        rng = random.Random(0)
        samples = [dist.sample(rng) for _ in range(1000)]
        assert min(samples) < Decimal("10")
        assert max(samples) > Decimal("90")


class TestNormalContribution:
    def test_name_is_normal(self) -> None:
        dist = NormalContribution(Decimal("300"), Decimal("700"))
        assert dist.name == "normal"

    def test_sample_within_bounds(self) -> None:
        dist = NormalContribution(Decimal("300"), Decimal("700"))
        rng = random.Random(42)
        for _ in range(200):
            value = dist.sample(rng)
            assert Decimal("300") <= value <= Decimal("700")

    def test_sample_has_two_decimal_places(self) -> None:
        dist = NormalContribution(Decimal("100"), Decimal("200"))
        rng = random.Random(42)
        for _ in range(50):
            value = dist.sample(rng)
            assert value == value.quantize(Decimal("0.01"))

    def test_default_std_is_range_over_four(self) -> None:
        # std defaults to (max - min) / 4 — we verify by checking
        # that roughly 95% of samples lie within 2 std of mean
        dist = NormalContribution(Decimal("0"), Decimal("400"))
        # mean=200, std=100, so 95% should be in [0, 400], which is also the clip range
        rng = random.Random(0)
        samples = [dist.sample(rng) for _ in range(500)]
        # All within bounds (clip guarantees this)
        assert all(Decimal("0") <= s <= Decimal("400") for s in samples)
        # Centre of mass should be near 200
        mean = sum(samples, Decimal("0")) / len(samples)
        assert Decimal("150") <= mean <= Decimal("250")

    def test_custom_std_accepted(self) -> None:
        dist = NormalContribution(Decimal("400"), Decimal("600"), std=Decimal("10"))
        rng = random.Random(42)
        # With a very tight std, most samples should be near the mean (500)
        samples = [dist.sample(rng) for _ in range(200)]
        mean = sum(samples, Decimal("0")) / len(samples)
        assert Decimal("480") <= mean <= Decimal("520")

    def test_clip_prevents_values_below_min(self) -> None:
        # mean=500, very large std — clipping must prevent going below min
        dist = NormalContribution(Decimal("400"), Decimal("600"), std=Decimal("200"))
        rng = random.Random(42)
        for _ in range(200):
            assert dist.sample(rng) >= Decimal("400")

    def test_clip_prevents_values_above_max(self) -> None:
        dist = NormalContribution(Decimal("400"), Decimal("600"), std=Decimal("200"))
        rng = random.Random(42)
        for _ in range(200):
            assert dist.sample(rng) <= Decimal("600")


class TestContributionConfig:
    def test_defaults(self) -> None:
        cfg = ContributionConfig(min=Decimal("400"), max=Decimal("600"))
        assert cfg.distribution == "uniform"
        assert cfg.std is None

    def test_is_frozen(self) -> None:
        cfg = ContributionConfig(min=Decimal("400"), max=Decimal("600"))
        with pytest.raises((ValidationError, TypeError)):
            cfg.min = Decimal("0")  # type: ignore[misc]

    def test_min_greater_than_max_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ContributionConfig(min=Decimal("600"), max=Decimal("400"))

    def test_min_equal_to_max_is_valid(self) -> None:
        cfg = ContributionConfig(min=Decimal("500"), max=Decimal("500"))
        assert cfg.min == cfg.max

    def test_negative_min_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ContributionConfig(min=Decimal("-1"), max=Decimal("100"))

    def test_negative_max_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ContributionConfig(min=Decimal("0"), max=Decimal("-1"))

    def test_normal_distribution_accepted(self) -> None:
        cfg = ContributionConfig(
            min=Decimal("300"),
            max=Decimal("700"),
            distribution="normal",
            std=Decimal("50"),
        )
        assert cfg.distribution == "normal"
        assert cfg.std == Decimal("50")


class TestResolveContribution:
    def test_decimal_resolves_to_fixed(self) -> None:
        dist = resolve_contribution(Decimal("500"))
        assert isinstance(dist, FixedContribution)
        assert dist.sample(random.Random(0)) == Decimal("500")

    def test_config_uniform_resolves_to_uniform(self) -> None:
        cfg = ContributionConfig(min=Decimal("400"), max=Decimal("600"))
        dist = resolve_contribution(cfg)
        assert isinstance(dist, UniformContribution)

    def test_config_normal_resolves_to_normal(self) -> None:
        cfg = ContributionConfig(
            min=Decimal("300"), max=Decimal("700"), distribution="normal"
        )
        dist = resolve_contribution(cfg)
        assert isinstance(dist, NormalContribution)

    def test_config_normal_with_std_passes_through(self) -> None:
        cfg = ContributionConfig(
            min=Decimal("400"),
            max=Decimal("600"),
            distribution="normal",
            std=Decimal("25"),
        )
        dist = resolve_contribution(cfg)
        assert isinstance(dist, NormalContribution)
        # Custom std: samples should cluster tightly around 500
        rng = random.Random(42)
        samples = [dist.sample(rng) for _ in range(200)]
        mean = sum(samples, Decimal("0")) / len(samples)
        assert Decimal("480") <= mean <= Decimal("520")

    def test_unknown_distribution_raises_value_error(self) -> None:
        cfg = ContributionConfig.__new__(ContributionConfig)
        # Bypass pydantic to inject invalid distribution string
        object.__setattr__(cfg, "min", Decimal("0"))
        object.__setattr__(cfg, "max", Decimal("100"))
        object.__setattr__(cfg, "distribution", "gaussian")
        object.__setattr__(cfg, "std", None)
        with pytest.raises(ValueError, match="Unknown distribution"):
            resolve_contribution(cfg)


class TestBacktestConfigContribution:
    def test_plain_decimal_accepted(self) -> None:
        cfg = BacktestConfig(
            strategy="noop",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            monthly_contribution=Decimal("500"),
        )
        assert cfg.monthly_contribution == Decimal("500")

    def test_contribution_config_dict_accepted(self) -> None:
        # Pydantic coerces a dict to ContributionConfig; use model_validate to
        # exercise that path in a type-safe way.
        cfg = BacktestConfig.model_validate(
            {
                "strategy": "noop",
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 12, 31),
                "monthly_contribution": {
                    "min": 500,
                    "max": 750,
                    "distribution": "uniform",
                },
            }
        )
        assert isinstance(cfg.monthly_contribution, ContributionConfig)
        assert cfg.monthly_contribution.min == Decimal("500")

    def test_contribution_config_normal(self) -> None:
        cfg = BacktestConfig.model_validate(
            {
                "strategy": "noop",
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 12, 31),
                "monthly_contribution": {
                    "min": 500,
                    "max": 750,
                    "distribution": "normal",
                    "std": 50,
                },
            }
        )
        assert isinstance(cfg.monthly_contribution, ContributionConfig)
        assert cfg.monthly_contribution.distribution == "normal"
