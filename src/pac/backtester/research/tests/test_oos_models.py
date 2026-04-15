"""Tests for OOS result models."""

from __future__ import annotations

from datetime import date

import pytest

from pac.backtester.research.models import (
    EventAnalysisResult,
    EventMetrics,
    OOSResult,
    WalkForwardResult,
    WFWindow,
)


class TestOOSResult:
    def test_oos_result_frozen(self) -> None:
        r = OOSResult(
            split_date=date(2020, 6, 1),
            in_sample_metrics={"sharpe": 0.5},
            out_of_sample_metrics={"sharpe": 0.3},
            in_sample_final_value=110.0,
            out_of_sample_final_value=105.0,
            degradation_ratio=0.6,
        )
        assert r.split_date == date(2020, 6, 1)
        assert r.degradation_ratio == 0.6
        with pytest.raises(Exception):  # noqa: B017
            r.split_date = date(2021, 1, 1)  # type: ignore[misc]


class TestWFWindow:
    def test_wf_window_frozen(self) -> None:
        w = WFWindow(
            window_index=0,
            is_start=date(2010, 1, 1),
            is_end=date(2020, 1, 1),
            oos_start=date(2020, 1, 2),
            oos_end=date(2025, 1, 1),
            is_metrics={"sharpe": 0.5},
            oos_metrics={"sharpe": 0.4},
        )
        assert w.window_index == 0
        with pytest.raises(Exception):  # noqa: B017
            w.window_index = 1  # type: ignore[misc]


class TestWalkForwardResult:
    def test_walk_forward_result(self) -> None:
        windows = [
            WFWindow(
                window_index=0,
                is_start=date(2010, 1, 1),
                is_end=date(2020, 1, 1),
                oos_start=date(2020, 1, 2),
                oos_end=date(2025, 1, 1),
                is_metrics={"sharpe": 0.5},
                oos_metrics={"sharpe": 0.4},
            )
        ]
        r = WalkForwardResult(
            windows=windows,
            strategy="test",
            params={"a": 1},
            metric_names=["sharpe"],
            stability_score=1.5,
            consistent_windows=1,
        )
        assert r.strategy == "test"
        assert r.stability_score == 1.5
        assert r.consistent_windows == 1
        assert len(r.windows) == 1


class TestEventMetrics:
    def test_event_metrics(self) -> None:
        em = EventMetrics(
            event_name="COVID crash",
            event_start=date(2020, 2, 19),
            event_end=date(2020, 3, 23),
            event_tags=["crisis", "pandemic"],
            metrics_during_event={"sharpe": -0.5},
            event_return=-0.15,
        )
        assert em.event_name == "COVID crash"
        assert em.event_tags == ["crisis", "pandemic"]
        assert em.event_return == -0.15


class TestEventAnalysisResult:
    def test_event_analysis_result(self) -> None:
        per_event = [
            EventMetrics(
                event_name="A",
                event_start=date(2020, 1, 1),
                event_end=date(2020, 3, 1),
                event_tags=["crisis"],
                metrics_during_event={"sharpe": 0.3},
                event_return=0.05,
            ),
            EventMetrics(
                event_name="B",
                event_start=date(2020, 6, 1),
                event_end=date(2020, 9, 1),
                event_tags=["bull"],
                metrics_during_event={"sharpe": 0.8},
                event_return=0.10,
            ),
        ]
        r = EventAnalysisResult(
            calendar_name="test",
            strategy="crisis_exploit",
            params={},
            metric_names=["sharpe"],
            per_event=per_event,
            mean_event_return=0.075,
            generalization_score=0.5,
        )
        assert r.calendar_name == "test"
        assert len(r.per_event) == 2
        assert r.mean_event_return == 0.075
        assert r.generalization_score == 0.5
