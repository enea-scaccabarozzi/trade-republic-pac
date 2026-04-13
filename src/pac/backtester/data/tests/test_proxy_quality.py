from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pac.backtester.data.models import Interval, PriceBar, PriceSeries
from pac.backtester.data.proxy_quality import assess_proxy_quality


def _bar(d: date, close: float) -> PriceBar:
    c = Decimal(str(close))
    return PriceBar(date=d, open=c, high=c, low=c, close=c, volume=1000)


def _correlated_series(
    n: int,
    base_start: float,
    noise_pct: float,
    ticker: str,
    start: date | None = None,
) -> list[PriceBar]:
    """Generate price bars with deterministic returns + noise."""
    import math

    d = start or date(2020, 1, 1)
    bars: list[PriceBar] = []
    price = base_start
    for i in range(n):
        bars.append(_bar(d, price))
        # Sine wave return + noise
        ret = 0.001 * math.sin(i * 0.1) + noise_pct * ((i % 7) - 3) / 1000
        price *= 1 + ret
        d += timedelta(days=1)
        # Skip weekends
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return bars


class TestAssessProxyQuality:
    def test_high_correlation_good(self) -> None:
        """Nearly identical series → 'good' quality."""
        start = date(2020, 1, 1)
        bars_a = _correlated_series(200, 100.0, 0.01, "A", start=start)
        bars_b = _correlated_series(200, 100.0, 0.01, "B", start=start)
        proxy = PriceSeries(ticker="A", interval=Interval.DAILY, bars=bars_a)
        target = PriceSeries(ticker="B", interval=Interval.DAILY, bars=bars_b)

        report = assess_proxy_quality(proxy, target)

        assert report.quality == "good"
        assert report.correlation > 0.90

    def test_medium_correlation_warning(self) -> None:
        """Moderately correlated series → 'warning' quality."""
        start = date(2020, 1, 1)
        bars_a = _correlated_series(200, 100.0, 0.01, "A", start=start)
        # Different noise pattern → lower correlation
        bars_b = []
        d = start
        price = 100.0
        for i in range(200):
            bars_b.append(_bar(d, price))
            import math

            ret = 0.001 * math.sin(i * 0.1) + 0.005 * math.cos(i * 0.3)
            price *= 1 + ret
            d += timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)

        proxy = PriceSeries(ticker="A", interval=Interval.DAILY, bars=bars_a)
        target = PriceSeries(ticker="B", interval=Interval.DAILY, bars=bars_b)

        report = assess_proxy_quality(proxy, target)

        assert report.quality in ("warning", "poor")
        assert report.correlation < 0.90

    def test_low_correlation_poor(self) -> None:
        """Inversely correlated series → 'poor' quality."""
        start = date(2020, 1, 1)
        # Series A: goes up
        bars_a = []
        d = start
        price = 100.0
        for _i in range(200):
            bars_a.append(_bar(d, price))
            price *= 1.002
            d += timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)

        # Series B: goes down
        bars_b = []
        d = start
        price = 100.0
        for _i in range(200):
            bars_b.append(_bar(d, price))
            price *= 0.998
            d += timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)

        proxy = PriceSeries(ticker="A", interval=Interval.DAILY, bars=bars_a)
        target = PriceSeries(ticker="B", interval=Interval.DAILY, bars=bars_b)

        report = assess_proxy_quality(proxy, target)

        assert report.quality == "poor"
        assert report.correlation < 0.70

    def test_vol_ratio_outside_range_warning(self) -> None:
        """High vol ratio with high correlation → 'warning'."""
        start = date(2020, 1, 1)
        # Same direction, but proxy 3x more volatile
        bars_a = []
        bars_b = []
        d = start
        price_a = 100.0
        price_b = 100.0
        for i in range(200):
            bars_a.append(_bar(d, price_a))
            bars_b.append(_bar(d, price_b))
            import math

            base_ret = 0.005 * math.sin(i * 0.05)
            price_a *= 1 + base_ret * 3  # 3x vol
            price_b *= 1 + base_ret
            d += timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)

        proxy = PriceSeries(ticker="A", interval=Interval.DAILY, bars=bars_a)
        target = PriceSeries(ticker="B", interval=Interval.DAILY, bars=bars_b)

        report = assess_proxy_quality(proxy, target)

        # Correlation should be high, but vol ratio outside [0.7, 1.4]
        assert report.vol_ratio > 1.4 or report.vol_ratio < 0.7
        assert any("Vol ratio" in issue for issue in report.issues)

    def test_insufficient_overlap_warning(self) -> None:
        """Few overlap days triggers overlap warning."""
        start = date(2020, 1, 1)
        bars = [_bar(start + timedelta(days=i), 100.0 + i * 0.1) for i in range(10)]
        proxy = PriceSeries(ticker="A", interval=Interval.DAILY, bars=bars)
        target = PriceSeries(ticker="B", interval=Interval.DAILY, bars=bars)

        report = assess_proxy_quality(proxy, target)

        assert any("overlap days" in issue for issue in report.issues)

    def test_no_overlap_data_poor(self) -> None:
        """Non-overlapping series → 'poor' quality."""
        bars_a = [_bar(date(2020, 1, i), 100.0) for i in range(1, 4)]
        bars_b = [_bar(date(2021, 1, i), 100.0) for i in range(1, 4)]

        proxy = PriceSeries(ticker="A", interval=Interval.DAILY, bars=bars_a)
        target = PriceSeries(ticker="B", interval=Interval.DAILY, bars=bars_b)

        report = assess_proxy_quality(proxy, target)

        assert report.quality == "poor"
        assert report.overlap_days == 0
