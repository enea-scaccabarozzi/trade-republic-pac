from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from pac.backtester.engine.simulator import IterationResult
from pac.backtester.metrics.returns import equity_to_returns
from pac.backtester.metrics.tests.conftest import _make_iteration


class TestEquityToReturns:
    def test_basic_equity_to_returns(self) -> None:
        iteration = _make_iteration([100, 105, 110])
        returns = equity_to_returns(iteration)

        assert len(returns) == 2
        assert returns.iloc[0] == pytest.approx(0.05)
        assert returns.iloc[1] == pytest.approx(0.047619, abs=1e-4)

    def test_single_day_returns_empty(self) -> None:
        iteration = _make_iteration([100])
        returns = equity_to_returns(iteration)

        assert len(returns) == 0

    def test_empty_daily_values_returns_empty(self) -> None:
        iteration = IterationResult(
            iteration=0,
            daily_values=[],
            trades=[],
            final_value=Decimal("0"),
        )
        returns = equity_to_returns(iteration)

        assert len(returns) == 0

    def test_returns_index_is_datetime(self) -> None:
        iteration = _make_iteration([100, 105, 110])
        returns = equity_to_returns(iteration)

        assert isinstance(returns.index, pd.DatetimeIndex)

    def test_returns_are_float(self) -> None:
        iteration = _make_iteration([100, 105, 110])
        returns = equity_to_returns(iteration)

        for val in returns:
            assert isinstance(val, float)

    def test_constant_equity_returns_zero(self) -> None:
        iteration = _make_iteration([100, 100, 100])
        returns = equity_to_returns(iteration)

        assert len(returns) == 2
        assert returns.iloc[0] == pytest.approx(0.0)
        assert returns.iloc[1] == pytest.approx(0.0)

    def test_equity_with_drawdown(self) -> None:
        iteration = _make_iteration([100, 90, 95])
        returns = equity_to_returns(iteration)

        assert len(returns) == 2
        assert returns.iloc[0] == pytest.approx(-0.1)
        assert returns.iloc[1] == pytest.approx(0.05556, abs=1e-4)
