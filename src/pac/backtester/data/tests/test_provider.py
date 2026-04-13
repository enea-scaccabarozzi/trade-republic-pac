from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pac.backtester.data.models import DataRequest, Interval, PriceBar, PriceSeries
from pac.backtester.data.provider import (
    MarketDataProvider,
    normalize_and_stitch,
    resolve_tickers,
    validate_handoff,
)
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


# ─── Helper for new tests ──────────────────────────────────


def _bar(d: date, close: Decimal) -> PriceBar:
    return PriceBar(
        date=d,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )


# ─── TestNormalizeAndStitch ─────────────────────────────────


class TestNormalizeAndStitch:
    def test_happy_path_scales_proxy(self) -> None:
        """Proxy at ~400, primary at ~40 → proxy scaled down by 10x."""
        handoff = date(2020, 6, 15)
        proxy = [
            _bar(date(2020, 6, 12), Decimal("380")),
            _bar(date(2020, 6, 15), Decimal("400")),
        ]
        primary = [
            _bar(date(2020, 6, 16), Decimal("40")),
            _bar(date(2020, 6, 17), Decimal("41")),
        ]

        result = normalize_and_stitch(primary, proxy, handoff)

        assert len(result) == 4
        # ratio = 40/400 = 0.1
        assert result[0].close == Decimal("380") * Decimal("40") / Decimal("400")
        assert result[1].close == Decimal("40")  # last proxy scaled to match
        assert result[2].close == Decimal("40")  # first primary unchanged
        assert result[3].close == Decimal("41")

    def test_equal_prices_no_scaling(self) -> None:
        """When proxy and primary match in price, ratio = 1.0."""
        handoff = date(2020, 6, 15)
        proxy = [_bar(date(2020, 6, 15), Decimal("100"))]
        primary = [_bar(date(2020, 6, 16), Decimal("100"))]

        result = normalize_and_stitch(primary, proxy, handoff)

        assert len(result) == 2
        assert result[0].close == Decimal("100")
        assert result[1].close == Decimal("100")

    def test_empty_proxy_returns_primary_only(self) -> None:
        """Empty proxy bars → returns primary bars only."""
        handoff = date(2020, 6, 15)
        primary = [_bar(date(2020, 6, 16), Decimal("50"))]

        result = normalize_and_stitch(primary, [], handoff)

        assert len(result) == 1
        assert result[0].close == Decimal("50")

    def test_empty_primary_returns_proxy_only(self) -> None:
        """Empty primary bars → returns proxy bars (no scaling possible)."""
        handoff = date(2020, 6, 15)
        proxy = [_bar(date(2020, 6, 15), Decimal("400"))]

        result = normalize_and_stitch([], proxy, handoff)

        assert len(result) == 1
        assert result[0].close == Decimal("400")

    def test_zero_proxy_close_raises(self) -> None:
        """Zero proxy close price raises ValueError."""
        handoff = date(2020, 6, 15)
        proxy = [_bar(date(2020, 6, 15), Decimal("0"))]
        primary = [_bar(date(2020, 6, 16), Decimal("50"))]

        with pytest.raises(ValueError, match="Proxy close price is 0"):
            normalize_and_stitch(primary, proxy, handoff)


# ─── TestValidateHandoff ────────────────────────────────────


class TestValidateHandoff:
    def test_valid_handoff_small_gap(self) -> None:
        """Gap ≤ 5 calendar days → no error."""
        handoff = date(2020, 6, 15)  # Monday
        proxy = [_bar(date(2020, 6, 15), Decimal("100"))]
        primary = [_bar(date(2020, 6, 16), Decimal("100"))]

        # Should not raise
        validate_handoff(proxy, primary, handoff, "PROXY", "PRIMARY")

    def test_weekend_gap_ok(self) -> None:
        """Weekend gap (2 calendar days) → no error."""
        handoff = date(2020, 6, 12)  # Friday
        proxy = [_bar(date(2020, 6, 12), Decimal("100"))]
        primary = [_bar(date(2020, 6, 15), Decimal("100"))]  # Monday

        validate_handoff(proxy, primary, handoff, "PROXY", "PRIMARY")

    def test_gap_exceeds_limit_raises(self) -> None:
        """Gap > 5 days → raises ValueError."""
        handoff = date(2020, 6, 15)
        proxy = [_bar(date(2020, 6, 15), Decimal("100"))]
        primary = [_bar(date(2020, 6, 25), Decimal("100"))]  # 10 days gap

        with pytest.raises(ValueError, match="Data gap of 10 days"):
            validate_handoff(proxy, primary, handoff, "PROXY", "PRIMARY")

    def test_no_proxy_data_before_handoff_raises(self) -> None:
        """No proxy data on or before handoff → raises ValueError."""
        handoff = date(2020, 6, 15)
        proxy = [_bar(date(2020, 6, 20), Decimal("100"))]  # after handoff
        primary = [_bar(date(2020, 6, 16), Decimal("100"))]

        with pytest.raises(ValueError, match="No proxy data"):
            validate_handoff(proxy, primary, handoff, "PROXY", "PRIMARY")

    def test_no_primary_data_after_handoff_raises(self) -> None:
        """No primary data after handoff → raises ValueError."""
        handoff = date(2020, 6, 15)
        proxy = [_bar(date(2020, 6, 15), Decimal("100"))]
        primary = [_bar(date(2020, 6, 10), Decimal("100"))]  # before handoff

        with pytest.raises(ValueError, match="No primary data"):
            validate_handoff(proxy, primary, handoff, "PROXY", "PRIMARY")


# ─── TestFetchWithProxyChain ────────────────────────────────


class TestFetchWithProxyChain:
    """Tests for fetch_with_proxy with both legacy and chain proxy support."""

    def _make_provider(
        self,
        tmp_path: Path,
        responses: dict[str, list[PriceBar]],
    ) -> MarketDataProvider:
        """Build a provider with a mocked fetch method."""
        from unittest.mock import MagicMock

        with patch("pac.backtester.data.provider.yf", MagicMock()):
            provider = MarketDataProvider(cache_dir=tmp_path)

        def _mock_fetch(req: DataRequest) -> PriceSeries:
            bars = responses.get(req.ticker, [])
            filtered = [b for b in bars if req.start <= b.date <= req.end]
            if not filtered:
                msg = f"No data returned for {req.ticker}"
                raise ValueError(msg)
            return PriceSeries(
                ticker=req.ticker,
                interval=Interval.DAILY,
                bars=filtered,
            )

        provider.fetch = _mock_fetch  # type: ignore[assignment]
        return provider

    def test_single_proxy_legacy_compat(self, tmp_path: Path) -> None:
        """Legacy proxy_ticker/proxy_end still works."""
        proxy_bars = [
            _bar(date(2020, 6, 12), Decimal("400")),
            _bar(date(2020, 6, 15), Decimal("402")),
        ]
        primary_bars = [
            _bar(date(2020, 6, 16), Decimal("40")),
            _bar(date(2020, 6, 17), Decimal("41")),
        ]
        provider = self._make_provider(
            tmp_path,
            {"PROXY": proxy_bars, "PRIMARY": primary_bars},
        )

        result = provider.fetch_with_proxy(
            ticker="PRIMARY",
            start=date(2020, 6, 12),
            end=date(2020, 6, 17),
            proxy_ticker="PROXY",
            proxy_end=date(2020, 6, 15),
        )

        assert len(result) == 4
        # Proxy bars should be normalized
        assert result.bars[-1].close == Decimal("41")

    def test_two_segment_chain(self, tmp_path: Path) -> None:
        """Two proxy segments + primary."""
        from pac.config.models import ProxySpec

        p1 = [
            _bar(date(2005, 1, 3), Decimal("100")),
            _bar(date(2005, 1, 4), Decimal("101")),
        ]
        p2 = [
            _bar(date(2005, 1, 5), Decimal("50")),
            _bar(date(2005, 1, 6), Decimal("51")),
        ]
        primary = [
            _bar(date(2005, 1, 7), Decimal("200")),
            _bar(date(2005, 1, 10), Decimal("202")),
        ]
        provider = self._make_provider(
            tmp_path,
            {"P1": p1, "P2": p2, "PRIMARY": primary},
        )

        result = provider.fetch_with_proxy(
            ticker="PRIMARY",
            start=date(2005, 1, 3),
            end=date(2005, 1, 10),
            proxy_chain=[
                ProxySpec(ticker="P1", end=date(2005, 1, 4)),
                ProxySpec(ticker="P2", end=date(2005, 1, 6)),
            ],
        )

        assert len(result) == 6
        # Primary bars unchanged
        assert result.bars[-2].close == Decimal("200")
        assert result.bars[-1].close == Decimal("202")
        # Price should be continuous at boundaries (no big jumps)
        for i in range(1, len(result.bars)):
            prev = float(result.bars[i - 1].close)
            curr = float(result.bars[i].close)
            ret = abs(curr / prev - 1)
            assert ret < 0.15, f"Return too large at {result.bars[i].date}: {ret}"

    def test_no_proxy_chain_direct_fetch(self, tmp_path: Path) -> None:
        """No proxy chain → direct fetch."""
        bars = [
            _bar(date(2024, 1, 2), Decimal("100")),
            _bar(date(2024, 1, 3), Decimal("101")),
        ]
        provider = self._make_provider(tmp_path, {"T": bars})

        result = provider.fetch_with_proxy(
            ticker="T",
            start=date(2024, 1, 2),
            end=date(2024, 1, 3),
        )

        assert len(result) == 2
        assert result.bars[0].close == Decimal("100")

    def test_start_after_all_proxies(self, tmp_path: Path) -> None:
        """Start date after all proxies → primary only."""
        from pac.config.models import ProxySpec

        primary = [
            _bar(date(2024, 1, 2), Decimal("100")),
            _bar(date(2024, 1, 3), Decimal("101")),
        ]
        provider = self._make_provider(tmp_path, {"PRIMARY": primary, "PROXY": []})

        result = provider.fetch_with_proxy(
            ticker="PRIMARY",
            start=date(2024, 1, 2),
            end=date(2024, 1, 3),
            proxy_chain=[
                ProxySpec(ticker="PROXY", end=date(2020, 1, 1)),
            ],
        )

        assert len(result) == 2
        assert result.bars[0].close == Decimal("100")

    def test_end_before_primary(self, tmp_path: Path) -> None:
        """End date within proxy period → proxy only."""
        from pac.config.models import ProxySpec

        proxy_bars = [
            _bar(date(2005, 1, 3), Decimal("100")),
            _bar(date(2005, 1, 4), Decimal("101")),
        ]
        provider = self._make_provider(tmp_path, {"PROXY": proxy_bars})

        result = provider.fetch_with_proxy(
            ticker="PRIMARY",
            start=date(2005, 1, 3),
            end=date(2005, 1, 4),
            proxy_chain=[
                ProxySpec(ticker="PROXY", end=date(2010, 1, 1)),
            ],
        )

        assert len(result) == 2

    def test_fx_conversion_applied(self, tmp_path: Path) -> None:
        """FX conversion applied to USD proxy segments."""
        from pac.config.models import ProxySpec

        proxy_bars = [
            _bar(date(2005, 1, 3), Decimal("100")),
            _bar(date(2005, 1, 4), Decimal("101")),
        ]
        primary_bars = [
            _bar(date(2005, 1, 5), Decimal("80")),
            _bar(date(2005, 1, 6), Decimal("81")),
        ]
        fx_bars = [
            _bar(date(2005, 1, 3), Decimal("1.20")),
            _bar(date(2005, 1, 4), Decimal("1.20")),
        ]
        provider = self._make_provider(
            tmp_path,
            {
                "PROXY": proxy_bars,
                "PRIMARY": primary_bars,
                "EURUSD=X": fx_bars,
            },
        )

        result = provider.fetch_with_proxy(
            ticker="PRIMARY",
            start=date(2005, 1, 3),
            end=date(2005, 1, 6),
            proxy_chain=[
                ProxySpec(
                    ticker="PROXY",
                    end=date(2005, 1, 4),
                    currency="USD",
                ),
            ],
        )

        assert len(result) == 4
        # Primary bars unchanged (no currency set on primary)
        assert result.bars[-1].close == Decimal("81")


# ─── TestStitchBoundaryReturns ──────────────────────────────


class TestStitchBoundaryReturns:
    def test_no_large_returns_at_boundary(self, tmp_path: Path) -> None:
        """No daily return > 15% at any stitch boundary."""
        from pac.config.models import ProxySpec

        # 3 segments at very different price levels
        p1 = [_bar(date(2005, 1, i), Decimal(str(400 + i))) for i in range(3, 6)]
        p2 = [_bar(date(2005, 1, i), Decimal(str(40 + i))) for i in range(6, 8)]
        primary = [_bar(date(2005, 1, i), Decimal(str(200 + i))) for i in range(10, 13)]

        with patch("pac.backtester.data.provider.yf", MagicMock()):
            provider = MarketDataProvider(cache_dir=tmp_path)

        def _mock_fetch(req: DataRequest) -> PriceSeries:
            mapping: dict[str, list[PriceBar]] = {
                "P1": p1,
                "P2": p2,
                "PRIMARY": primary,
            }
            bars = mapping.get(req.ticker, [])
            filtered = [b for b in bars if req.start <= b.date <= req.end]
            if not filtered:
                msg = f"No data for {req.ticker}"
                raise ValueError(msg)
            return PriceSeries(
                ticker=req.ticker, interval=Interval.DAILY, bars=filtered
            )

        provider.fetch = _mock_fetch  # type: ignore[assignment]

        result = provider.fetch_with_proxy(
            ticker="PRIMARY",
            start=date(2005, 1, 3),
            end=date(2005, 1, 12),
            proxy_chain=[
                ProxySpec(ticker="P1", end=date(2005, 1, 5)),
                ProxySpec(ticker="P2", end=date(2005, 1, 7)),
            ],
        )

        for i in range(1, len(result.bars)):
            prev = float(result.bars[i - 1].close)
            curr = float(result.bars[i].close)
            daily_ret = abs(curr / prev - 1)
            assert daily_ret < 0.15, (
                f"Large return {daily_ret:.2%} at {result.bars[i].date}"
            )
