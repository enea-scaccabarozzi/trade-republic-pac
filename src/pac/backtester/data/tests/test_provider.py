from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pac.backtester.data.models import DataRequest, Interval, PriceSeries
from pac.backtester.data.provider import MarketDataProvider, resolve_tickers
from pac.config.models import Settings


def _make_settings(**overrides: Any) -> Settings:
    """Build a Settings instance with test defaults for ticker tests."""
    base: dict[str, Any] = {
        "version": 1,
        "broker": {
            "type": "trade_republic",
            "phone_number": "+491234567890",
            "pin": "1234",
        },
        "assets": [
            {
                "id": "stocks",
                "name": "Stocks ETF",
                "isin": "IE00BK5BQT80",
                "ticker": "EUNL.DE",
                "target_pct": 70,
            },
            {
                "id": "gold",
                "name": "Gold ETC",
                "isin": "IE00B4ND3602",
                "ticker": "4GLD.DE",
                "target_pct": 15,
            },
            {
                "id": "bonds",
                "name": "Bond ETF",
                "isin": "IE00B3F81409",
                "ticker": "EUN4.DE",
                "target_pct": 15,
            },
        ],
        "app": {"job_secret": "test-job-secret"},
        "channels": {},
        "signals": [],
    }
    base.update(overrides)
    return Settings.model_validate(base)


def _make_df(rows: list[dict[str, Any]]) -> Any:
    """Build a pandas-like DataFrame stub from row dicts."""
    import pandas as pd

    df = pd.DataFrame(rows)
    if rows:
        df.index = pd.to_datetime(df.pop("Date"))
    return df


def _sample_df() -> Any:
    return _make_df(
        [
            {
                "Date": "2024-01-02",
                "Open": 100.0,
                "High": 105.0,
                "Low": 99.0,
                "Close": 103.5,
                "Volume": 1_000_000,
            },
            {
                "Date": "2024-01-03",
                "Open": 103.5,
                "High": 106.0,
                "Low": 102.0,
                "Close": 104.0,
                "Volume": 1_100_000,
            },
        ]
    )


class TestMarketDataProviderImportGuard:
    def test_import_error_when_yfinance_missing(self, tmp_path: Path) -> None:
        with (
            patch("pac.backtester.data.provider.yf", None),
            pytest.raises(ImportError, match="uv sync --group backtest"),
        ):
            MarketDataProvider(cache_dir=tmp_path)


class TestMarketDataProviderFetch:
    def test_fetch_returns_price_series(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            request = DataRequest(
                ticker="EUNL.DE",
                start=date(2024, 1, 1),
                end=date(2024, 1, 3),
            )
            series = provider.fetch(request)

        assert isinstance(series, PriceSeries)
        assert series.ticker == "EUNL.DE"
        assert len(series) == 2

    def test_fetch_empty_data_raises_value_error(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_df([])

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            request = DataRequest(
                ticker="XXXXXXXXX.XX",
                start=date(2024, 1, 1),
                end=date(2024, 3, 31),
            )
            with pytest.raises(ValueError, match="No data returned"):
                provider.fetch(request)

    def test_fetch_converts_floats_to_decimal(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            request = DataRequest(
                ticker="EUNL.DE",
                start=date(2024, 1, 1),
                end=date(2024, 1, 3),
            )
            series = provider.fetch(request)

        bar = series.bars[0]
        assert isinstance(bar.open, Decimal)
        assert isinstance(bar.high, Decimal)
        assert isinstance(bar.low, Decimal)
        assert isinstance(bar.close, Decimal)

    def test_fetch_passes_correct_params_to_yfinance(
        self,
        tmp_path: Path,
    ) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            request = DataRequest(
                ticker="EUNL.DE",
                start=date(2024, 1, 1),
                end=date(2024, 1, 3),
                interval=Interval.WEEKLY,
            )
            provider.fetch(request)

        mock_yf.Ticker.assert_called_once_with("EUNL.DE")
        mock_ticker.history.assert_called_once_with(
            start="2024-01-01",
            end="2024-01-04",  # end + 1 day
            interval="1wk",
            auto_adjust=True,
        )

    def test_fetch_end_date_adjusted(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            request = DataRequest(
                ticker="EUNL.DE",
                start=date(2024, 1, 1),
                end=date(2024, 3, 31),
            )
            provider.fetch(request)

        expected_end = (date(2024, 3, 31) + timedelta(days=1)).isoformat()
        call_args = mock_ticker.history.call_args
        assert call_args.kwargs["end"] == expected_end

    def test_fetch_multiple_returns_dict(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            requests = [
                DataRequest(
                    ticker="EUNL.DE",
                    start=date(2024, 1, 1),
                    end=date(2024, 1, 3),
                ),
                DataRequest(
                    ticker="4GLD.DE",
                    start=date(2024, 1, 1),
                    end=date(2024, 1, 3),
                ),
            ]
            result = provider.fetch_multiple(requests)

        assert len(result) == 2
        assert "EUNL.DE" in result
        assert "4GLD.DE" in result
        assert isinstance(result["EUNL.DE"], PriceSeries)


class TestMarketDataProviderCache:
    def test_cache_dir_created_on_init(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "new" / "cache"
        assert not cache_dir.exists()

        with patch("pac.backtester.data.provider.yf", MagicMock()):
            MarketDataProvider(cache_dir=cache_dir)

        assert cache_dir.exists()

    def test_cache_hit_skips_yfinance(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            request = DataRequest(
                ticker="EUNL.DE",
                start=date(2024, 1, 1),
                end=date(2024, 1, 3),
            )
            first = provider.fetch(request)
            second = provider.fetch(request)

        assert first == second
        # yf.Ticker should only be called once (cache hit on second call)
        assert mock_yf.Ticker.call_count == 1

    def test_cache_miss_when_expired(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path, cache_ttl=0)

            request = DataRequest(
                ticker="EUNL.DE",
                start=date(2024, 1, 1),
                end=date(2024, 1, 3),
            )
            provider.fetch(request)
            provider.fetch(request)

        # Both calls should hit yfinance since TTL is 0
        assert mock_yf.Ticker.call_count == 2

    def test_clear_cache_removes_files(self, tmp_path: Path) -> None:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_df()

        with patch("pac.backtester.data.provider.yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            provider = MarketDataProvider(cache_dir=tmp_path)

            for ticker in ["EUNL.DE", "4GLD.DE"]:
                provider.fetch(
                    DataRequest(
                        ticker=ticker,
                        start=date(2024, 1, 1),
                        end=date(2024, 1, 3),
                    )
                )

            count = provider.clear_cache()

        assert count == 2
        assert list(tmp_path.glob("*.json")) == []


class TestResolveTickers:
    def test_resolve_tickers_all_present(self) -> None:
        settings = _make_settings()
        result = resolve_tickers(settings)

        assert result == {
            "stocks": "EUNL.DE",
            "gold": "4GLD.DE",
            "bonds": "EUN4.DE",
        }

    def test_resolve_tickers_missing_raises(self) -> None:
        settings = _make_settings(
            assets=[
                {
                    "id": "stocks",
                    "name": "Stocks",
                    "isin": "IE00BK5BQT80",
                    "target_pct": 100,
                },
            ],
        )
        with pytest.raises(ValueError, match="missing 'ticker' field"):
            resolve_tickers(settings)

    def test_resolve_tickers_partial_missing(self) -> None:
        settings = _make_settings(
            assets=[
                {
                    "id": "stocks",
                    "name": "Stocks",
                    "isin": "IE00BK5BQT80",
                    "ticker": "EUNL.DE",
                    "target_pct": 70,
                },
                {
                    "id": "gold",
                    "name": "Gold",
                    "isin": "IE00B4ND3602",
                    "target_pct": 15,
                },
                {
                    "id": "bonds",
                    "name": "Bonds",
                    "isin": "IE00B3F81409",
                    "target_pct": 15,
                },
            ],
        )
        with pytest.raises(ValueError, match=r"gold.*bonds"):
            resolve_tickers(settings)
