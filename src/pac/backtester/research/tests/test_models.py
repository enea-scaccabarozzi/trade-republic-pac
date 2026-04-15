"""Tests for research data models."""

from __future__ import annotations

import pytest

from pac.backtester.research.models import (
    ComparisonTable,
    SweepResult,
    VariantResult,
)


class TestVariantResult:
    def test_is_frozen(self) -> None:
        vr = VariantResult(
            label="test",
            strategy="s",
            params={},
            final_value=100.0,
            metrics={"sharpe": 0.5},
        )
        with pytest.raises(Exception):  # noqa: B017
            vr.label = "other"  # type: ignore[misc]


class TestComparisonTable:
    def test_to_dict(self) -> None:
        v1 = VariantResult(
            label="A",
            strategy="s",
            params={},
            final_value=100.0,
            metrics={"sharpe": 0.5, "cagr": 0.08},
        )
        v2 = VariantResult(
            label="B",
            strategy="s",
            params={"x": 1},
            final_value=200.0,
            metrics={"sharpe": 0.6, "cagr": 0.1},
        )
        ct = ComparisonTable(
            variants=[v1, v2],
            metric_names=["sharpe", "cagr"],
        )
        d = ct.to_dict()
        assert set(d.keys()) == {"A", "B"}
        assert d["A"]["sharpe"] == 0.5
        assert d["A"]["final_value"] == 100.0
        assert d["B"]["cagr"] == 0.1


class TestSweepResult:
    def test_best_selects_max_primary_metric(self) -> None:
        variants = [
            VariantResult(
                label="low",
                strategy="s",
                params={"a": 1},
                final_value=100.0,
                metrics={"sharpe": 0.3, "cagr": 0.05},
            ),
            VariantResult(
                label="high",
                strategy="s",
                params={"a": 2},
                final_value=200.0,
                metrics={"sharpe": 0.9, "cagr": 0.12},
            ),
            VariantResult(
                label="mid",
                strategy="s",
                params={"a": 3},
                final_value=150.0,
                metrics={"sharpe": 0.6, "cagr": 0.08},
            ),
        ]
        sr = SweepResult(
            strategy="s",
            param_grid={"a": [1, 2, 3]},
            results=variants,
            metric_names=["sharpe", "cagr"],
        )
        assert sr.best.label == "high"

    def test_best_with_tie(self) -> None:
        variants = [
            VariantResult(
                label="x",
                strategy="s",
                params={"a": 1},
                final_value=100.0,
                metrics={"sharpe": 0.5},
            ),
            VariantResult(
                label="y",
                strategy="s",
                params={"a": 2},
                final_value=100.0,
                metrics={"sharpe": 0.5},
            ),
        ]
        sr = SweepResult(
            strategy="s",
            param_grid={"a": [1, 2]},
            results=variants,
            metric_names=["sharpe"],
        )
        # Deterministic — should return one without crashing
        assert sr.best.label in ("x", "y")
