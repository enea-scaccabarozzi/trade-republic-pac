#!/usr/bin/env python3
"""Generate figures and validate claims for the crisis strategy paper.

Uses production indicator functions and the real backtester engine to
ensure perfect consistency between the paper and the codebase.

Usage: python research/papers/crisis-strategy/generate_figures.py
Output: research/papers/crisis-strategy/figures/*.png + printed claim validation
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so `pac` is importable when running
# the script directly (python research/papers/crisis-strategy/generate_figures.py).
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

# --- visualization --------------------------------------------------------
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

# --- pac imports ----------------------------------------------------------
from pac.backtester.config import BacktestConfig  # noqa: E402
from pac.backtester.data.provider import MarketDataProvider  # noqa: E402
from pac.backtester.engine.simulator import (  # noqa: E402
    BacktestSimulator,
    IterationResult,
)
from pac.config.loader import load_config  # noqa: E402
from pac.models.market_data import PriceSeries  # noqa: E402
from pac.rules.builtin._indicators import (  # noqa: E402
    compute_death_cross,
    compute_divergence,
    compute_drawdown,
    compute_relative_strength,
)
from pac.rules.discovery import discover_rules  # noqa: E402
from pac.rules.registry import SignalRegistry  # noqa: E402

# ══════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════

START_DATE = date(2006, 1, 1)
END_DATE = date(2026, 4, 1)
INITIAL_EUR = Decimal("10000")
MONTHLY_PAC_EUR = Decimal("500")

# Crisis composite thresholds (from pac-backtest.yaml)
DD_DEPTH_THRESHOLD = -12.0  # drawdown_pct * 100 <= this
DD_VELOCITY_THRESHOLD = -0.25  # velocity * 100 <= this
DIVERGENCE_THRESHOLD = 12.0  # divergence * 100 >= this
RS_BREAKOUT_THRESHOLD = 8.0  # breakout_pct >= this (already %)
MIN_ACTIVE_INDICATORS = 3

# Indicator parameters
DRAWDOWN_LOOKBACK_BARS = 252
DIVERGENCE_LOOKBACK_BARS = 40
RS_MA_WINDOW = 120
DC_SHORT_WINDOW = 50
DC_LONG_WINDOW = 200
EQUITY_LOOKBACK_DAYS = 450  # calendar days (matches composite rule)
GOLD_LOOKBACK_DAYS = 250  # calendar days (matches composite rule)

# Known crisis windows for shading and heatmap
CRISIS_WINDOWS: dict[str, tuple[date, date]] = {
    "GFC 2008": (date(2007, 10, 9), date(2009, 3, 9)),
    "Euro Debt 2011": (date(2011, 7, 7), date(2011, 10, 3)),
    "COVID 2020": (date(2020, 2, 19), date(2020, 3, 23)),
    "Rate Hike 2022": (date(2022, 1, 3), date(2022, 10, 12)),
    "Tariff 2025": (date(2025, 2, 19), date(2025, 4, 1)),
}

# Strategy parameters (winning combo from Phase 6)
STRATEGY_PARAMS = {
    "pac_tilt_equity_pct": 100,
    "pac_tilt_gold_pct": 0,
    "pac_tilt_bond_pct": 0,
    "recovery_days": 120,
    "dd_threshold_pct": -20.0,
    "sell_fraction": 1.0,
    "cooldown_days": 90,
    "min_gold_pct": 5.0,
}

# Variant delta values from Phase 6 research (for fig4 bar chart).
# These are *relative* deltas measured during Phase 6 Monte Carlo runs
# against the Phase 6 baseline.  They may not sum to the actual
# single-path production alpha (see §7.8 in the paper).
VARIANT_DELTAS: dict[str, float] = {
    "H1 (90/5/5)": 10_526,
    "V5-120d (100/0/0)": 23_247,
    "H6 (hard rebal.)": 12_236,
    "Combined": 29_934,
}

FIGURES_DIR = Path(__file__).resolve().parent / "figures"
CONFIG_PATH = _PROJECT_ROOT / "backtest" / "pac-backtest.yaml"

# Shared style constants
_CRISIS_COLOR = "#ffcccc"
_CRISIS_ALPHA = 0.35
_SIGNAL_COLOR = "#2ca02c"
_BASELINE_COLOR = "#1f77b4"
_STRATEGY_COLOR = "#d62728"

# ══════════════════════════════════════════════════════════════════════════
# Data loading
# ══════════════════════════════════════════════════════════════════════════


def load_price_data() -> tuple[dict[str, PriceSeries], dict[str, str]]:
    """Load price data for all assets using proxy chains from config.

    Returns (ticker_to_series, asset_id_to_ticker) mappings.
    """
    settings = load_config(CONFIG_PATH)
    provider = MarketDataProvider()

    price_data: dict[str, PriceSeries] = {}
    asset_ticker_map: dict[str, str] = {}

    for asset in settings.assets:
        if asset.ticker is None:
            continue
        print(f"  Fetching {asset.id} ({asset.ticker})...")
        series = provider.fetch_with_proxy(
            ticker=asset.ticker,
            start=START_DATE,
            end=END_DATE,
            proxy_chain=asset.proxy_chain or None,
            primary_currency=asset.currency,
        )
        price_data[asset.ticker] = series
        asset_ticker_map[asset.id] = asset.ticker
        print(
            f"    {len(series.bars)} bars, " f"{series.start_date} to {series.end_date}"
        )

    return price_data, asset_ticker_map


# ══════════════════════════════════════════════════════════════════════════
# Indicator computation (day-by-day, no look-ahead)
# ══════════════════════════════════════════════════════════════════════════


def _in_crisis(d: date) -> bool:
    """Check whether a date falls inside any known crisis window."""
    return any(s <= d <= e for s, e in CRISIS_WINDOWS.values())


def compute_daily_indicators(
    price_data: dict[str, PriceSeries],
    asset_ticker_map: dict[str, str],
) -> dict[date, dict[str, bool]]:
    """Compute 5 crisis indicators for each trading day.

    Uses calendar-day-limited windows (same as BacktestMarketContext)
    to match production composite rule behavior exactly.
    Returns {date: {indicator_name: active_bool}}.
    """
    equity_ticker = asset_ticker_map["stocks"]
    gold_ticker = asset_ticker_map["gold"]

    equity_series = price_data[equity_ticker]
    gold_series = price_data[gold_ticker]

    # Use equity trading days as the reference calendar
    all_dates = [bar.date for bar in equity_series.bars]

    # Need enough history for the longest lookback (DC: 200+1 bars)
    min_warmup = DC_LONG_WINDOW + 1
    results: dict[date, dict[str, bool]] = {}

    for i, d in enumerate(all_dates):
        if i < min_warmup:
            continue

        # Slice using calendar-day windows (matching BacktestMarketContext)
        # Equity-only indicators use the larger equity window.
        # Dual-series indicators (divergence, RS) use gold window for BOTH
        # to keep index-based pairing date-aligned.
        eq_start = d - timedelta(days=EQUITY_LOOKBACK_DAYS)
        gold_start = d - timedelta(days=GOLD_LOOKBACK_DAYS)
        eq_window = equity_series.slice(eq_start, d)
        eq_window_short = equity_series.slice(gold_start, d)
        gold_window = gold_series.slice(gold_start, d)

        indicators: dict[str, bool] = {
            "dd_depth": False,
            "dd_velocity": False,
            "divergence": False,
            "death_cross": False,
            "rs_breakout": False,
        }

        # 1. Drawdown depth + velocity
        dd = None
        try:
            dd = compute_drawdown(eq_window, lookback_bars=DRAWDOWN_LOOKBACK_BARS)
            indicators["dd_depth"] = (dd.drawdown_pct * 100) <= DD_DEPTH_THRESHOLD
        except ValueError:
            pass

        # 2. Drawdown velocity
        if dd is not None and dd.days_since_peak > 0:
            indicators["dd_velocity"] = (dd.velocity * 100) <= DD_VELOCITY_THRESHOLD

        # 3. Gold-equity divergence
        try:
            div = compute_divergence(
                gold_window,
                eq_window_short,
                lookback_bars=DIVERGENCE_LOOKBACK_BARS,
            )
            indicators["divergence"] = (div.divergence * 100) >= DIVERGENCE_THRESHOLD
        except ValueError:
            pass

        # 4. Death cross
        try:
            dc = compute_death_cross(
                eq_window,
                short_window=DC_SHORT_WINDOW,
                long_window=DC_LONG_WINDOW,
            )
            indicators["death_cross"] = dc.bearish_regime
        except ValueError:
            pass

        # 5. Relative strength breakout
        try:
            rs = compute_relative_strength(
                gold_window,
                eq_window_short,
                ma_window=RS_MA_WINDOW,
            )
            indicators["rs_breakout"] = rs.breakout_pct >= RS_BREAKOUT_THRESHOLD
        except ValueError:
            pass

        results[d] = indicators

    return results


# ══════════════════════════════════════════════════════════════════════════
# Backtester simulation (real engine, single-path)
# ══════════════════════════════════════════════════════════════════════════


def _build_registry() -> SignalRegistry:
    rules = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rules.values():
        registry.register(rule_cls)
    return registry


def _run_simulation(
    strategy_name: str,
    strategy_params: dict,
    price_data: dict[str, PriceSeries],
    settings: object,
    registry: SignalRegistry,
) -> IterationResult:
    """Run a single-iteration backtest with the given strategy."""
    from pac.backtester.strategies.discovery import discover_strategies

    available = discover_strategies()
    strategy_cls = available[strategy_name]
    params = strategy_cls.params_model.model_validate(strategy_params)
    strategy = strategy_cls(params)

    config = BacktestConfig(
        strategy=strategy_name,
        strategy_params=strategy_params,
        start_date=START_DATE,
        end_date=END_DATE,
        initial_cash=INITIAL_EUR,
        monthly_contribution=MONTHLY_PAC_EUR,
        pac_execution_days=[2, 16],
        settlement_fee=Decimal("1.00"),
        spread_bps=Decimal("10"),
        slippage_days=(0, 0),
        monte_carlo_iterations=1,
        metrics=[],
        benchmark=False,
    )

    sim = BacktestSimulator(
        config,
        settings,  # type: ignore[arg-type]
        price_data,
        registry,
        strategy,
        rng_seed=42,
    )
    return sim.run_iteration(0)


def run_simulations(
    price_data: dict[str, PriceSeries],
    asset_ticker_map: dict[str, str],
) -> tuple[IterationResult, IterationResult]:
    """Run baseline (pac_alignment) and crisis_exploit strategy."""
    settings = load_config(CONFIG_PATH)
    registry = _build_registry()

    print("  Running baseline (pac_alignment)...")
    baseline = _run_simulation(
        "pac_alignment",
        {},
        price_data,
        settings,
        registry,
    )
    print(f"    Final value: {baseline.final_value}")

    print("  Running crisis_exploit strategy...")
    strategy = _run_simulation(
        "crisis_exploit",
        STRATEGY_PARAMS,
        price_data,
        settings,
        registry,
    )
    print(f"    Final value: {strategy.final_value}")

    return baseline, strategy


# ══════════════════════════════════════════════════════════════════════════
# Figure generation
# ══════════════════════════════════════════════════════════════════════════


def _shade_crises(ax: plt.Axes) -> None:  # type: ignore[name-defined]
    """Add semi-transparent crisis window shading to an axis."""
    for _name, (start, end) in CRISIS_WINDOWS.items():
        ax.axvspan(start, end, color=_CRISIS_COLOR, alpha=_CRISIS_ALPHA, zorder=0)


def _format_date_axis(ax: plt.Axes) -> None:  # type: ignore[name-defined]
    """Apply consistent date formatting to x-axis."""
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", rotation=30)


def _format_eur_axis(ax: plt.Axes, prefix: str = "") -> None:  # type: ignore[name-defined]
    """Format y-axis as EUR amounts."""
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"{prefix}{x:,.0f}")
    )


def generate_fig1(
    price_data: dict[str, PriceSeries],
    asset_ticker_map: dict[str, str],
    indicators: dict[date, dict[str, bool]],
) -> None:
    """Fig 1: Equity price line with composite signal overlay."""
    equity_ticker = asset_ticker_map["stocks"]
    eq_series = price_data[equity_ticker]

    dates = [bar.date for bar in eq_series.bars]
    closes = [float(bar.close) for bar in eq_series.bars]

    # Composite fire days: >= MIN_ACTIVE_INDICATORS active
    fire_dates = []
    fire_prices = []
    close_lookup = {bar.date: float(bar.close) for bar in eq_series.bars}
    for d, ind in indicators.items():
        active_count = sum(ind.values())
        if active_count >= MIN_ACTIVE_INDICATORS and d in close_lookup:
            fire_dates.append(d)
            fire_prices.append(close_lookup[d])

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(dates, closes, color=_BASELINE_COLOR, linewidth=0.8, label="Equity (EUR)")
    _shade_crises(ax)
    ax.scatter(
        fire_dates,
        fire_prices,
        color=_SIGNAL_COLOR,
        s=6,
        alpha=0.7,
        zorder=3,
        label=f"Composite fires ({len(fire_dates)} days)",
    )
    ax.set_title("Equity Price with Crisis Composite Signal Overlay", fontsize=13)
    ax.set_ylabel("Price (EUR)")
    ax.legend(loc="upper left", fontsize=9)
    _format_date_axis(ax)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig1_composite_signal_timeline.png", dpi=180)
    plt.close(fig)
    print("  Saved fig1_composite_signal_timeline.png")


def generate_fig2(
    indicators: dict[date, dict[str, bool]],
) -> None:
    """Fig 2: Indicator activation heatmap per crisis."""
    indicator_names = [
        "dd_depth",
        "dd_velocity",
        "divergence",
        "death_cross",
        "rs_breakout",
    ]
    display_names = [
        "DD Depth",
        "DD Velocity",
        "Divergence",
        "Death Cross",
        "RS Breakout",
    ]
    crisis_names = list(CRISIS_WINDOWS.keys())

    # Compute activation rates
    matrix: list[list[float]] = []
    for ind_name in indicator_names:
        row: list[float] = []
        for _crisis_name, (cs, ce) in CRISIS_WINDOWS.items():
            crisis_days = [d for d in indicators if cs <= d <= ce]
            if not crisis_days:
                row.append(0.0)
                continue
            active_count = sum(
                1 for d in crisis_days if indicators[d].get(ind_name, False)
            )
            row.append(100.0 * active_count / len(crisis_days))
        matrix.append(row)

    fig, ax = plt.subplots(figsize=(9, 5))
    im = ax.imshow(matrix, cmap="Greens", aspect="auto", vmin=0, vmax=100)

    ax.set_xticks(range(len(crisis_names)))
    ax.set_xticklabels(crisis_names, fontsize=9, rotation=25, ha="right")
    ax.set_yticks(range(len(display_names)))
    ax.set_yticklabels(display_names, fontsize=9)

    # Annotate cells
    for i in range(len(display_names)):
        for j in range(len(crisis_names)):
            val = matrix[i][j]
            color = "white" if val > 60 else "black"
            ax.text(
                j,
                i,
                f"{val:.0f}%",
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                color=color,
            )

    ax.set_title("Indicator Activation Rate per Crisis (%)", fontsize=13)
    fig.colorbar(im, ax=ax, label="Activation %", shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig2_indicator_heatmap.png", dpi=180)
    plt.close(fig)
    print("  Saved fig2_indicator_heatmap.png")


def generate_fig3(
    baseline: IterationResult,
    strategy: IterationResult,
) -> None:
    """Fig 3: Portfolio value — baseline vs strategy."""
    b_dates = [dr.date for dr in baseline.daily_values]
    b_vals = [float(dr.total_value) for dr in baseline.daily_values]
    s_dates = [dr.date for dr in strategy.daily_values]
    s_vals = [float(dr.total_value) for dr in strategy.daily_values]

    fig, ax = plt.subplots(figsize=(14, 5))
    _shade_crises(ax)
    ax.plot(
        b_dates,
        b_vals,
        color=_BASELINE_COLOR,
        linewidth=0.9,
        label="Baseline (70/15/15)",
    )
    ax.plot(
        s_dates, s_vals, color=_STRATEGY_COLOR, linewidth=0.9, label="Crisis Exploit"
    )

    # Annotate final values
    b_final = b_vals[-1]
    s_final = s_vals[-1]
    delta_pct = (s_final / b_final - 1) * 100
    ax.annotate(
        f"Baseline: \u20ac{b_final:,.0f}",
        xy=(b_dates[-1], b_final),
        xytext=(-140, -30),
        textcoords="offset points",
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color=_BASELINE_COLOR),
        color=_BASELINE_COLOR,
    )
    ax.annotate(
        f"Strategy: \u20ac{s_final:,.0f} (+{delta_pct:.1f}%)",
        xy=(s_dates[-1], s_final),
        xytext=(-180, 20),
        textcoords="offset points",
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color=_STRATEGY_COLOR),
        color=_STRATEGY_COLOR,
    )

    ax.set_title("Portfolio Value: Baseline vs Crisis Exploit Strategy", fontsize=13)
    ax.set_ylabel("Portfolio Value (EUR)")
    _format_date_axis(ax)
    _format_eur_axis(ax, prefix="\u20ac")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig3_portfolio_comparison.png", dpi=180)
    plt.close(fig)
    print("  Saved fig3_portfolio_comparison.png")


def generate_fig4(baseline_final: float) -> None:
    """Fig 4: PAC tilt variants bar chart (delta values from Phase 6)."""
    labels = ["Baseline", *list(VARIANT_DELTAS.keys())]
    values = [baseline_final] + [baseline_final + d for d in VARIANT_DELTAS.values()]

    colors = [_BASELINE_COLOR] + ["#ff7f0e"] * (len(labels) - 2) + [_STRATEGY_COLOR]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white", width=0.6)

    # Annotate bars with value and delta
    for i, (bar, val) in enumerate(zip(bars, values, strict=True)):
        label = f"\u20ac{val:,.0f}"
        if i > 0:
            delta = val - baseline_final
            label += f"\n(+\u20ac{delta:,.0f})"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 2000,
            label,
            ha="center",
            va="bottom",
            fontsize=8,
        )

    ax.set_title(
        "Strategy Variants: Final Portfolio Value"
        "\n(Phase 6 relative deltas — see §7.8)",
        fontsize=13,
    )
    ax.set_ylabel("Final Value (EUR)")
    _format_eur_axis(ax, prefix="\u20ac")
    ax.grid(True, axis="y", alpha=0.25)
    # Set y-axis to start from a reasonable baseline
    ax.set_ylim(bottom=baseline_final * 0.9)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig4_tilt_variants.png", dpi=180)
    plt.close(fig)
    print("  Saved fig4_tilt_variants.png")


def generate_fig5(
    strategy: IterationResult,
) -> None:
    """Fig 5: Cumulative contributions vs portfolio value."""
    dates = [dr.date for dr in strategy.daily_values]
    values = [float(dr.total_value) for dr in strategy.daily_values]

    # Compute cumulative contributions: initial + €500/month split over 2 PAC days.
    # Track by marking the first PAC execution of each (year, month) pair.
    cumulative: list[float] = []
    total_contributed = float(INITIAL_EUR)
    pac_days_set = {2, 16}
    seen_pac_events: set[tuple[int, int, int]] = set()  # (year, month, pac_day)

    for d in dates:
        if d.day in pac_days_set and d > dates[0]:
            key = (d.year, d.month, d.day)
            if key not in seen_pac_events:
                seen_pac_events.add(key)
                total_contributed += float(MONTHLY_PAC_EUR) / 2
        cumulative.append(total_contributed)

    fig, ax = plt.subplots(figsize=(14, 5))
    _shade_crises(ax)

    ax.fill_between(
        dates,
        0,
        cumulative,
        alpha=0.3,
        color="#aec7e8",
        label="Cumulative Contributions",
    )
    ax.plot(dates, cumulative, color=_BASELINE_COLOR, linewidth=0.7, alpha=0.8)
    ax.plot(
        dates,
        values,
        color=_STRATEGY_COLOR,
        linewidth=0.9,
        label="Portfolio Value (Strategy)",
    )

    # Annotate final gap
    final_contrib = cumulative[-1]
    final_value = values[-1]
    gain = final_value - final_contrib
    ax.annotate(
        f"Returns: \u20ac{gain:,.0f}",
        xy=(dates[-1], (final_value + final_contrib) / 2),
        xytext=(-150, 0),
        textcoords="offset points",
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color="gray"),
    )

    ax.set_title("Cumulative Contributions vs Portfolio Value", fontsize=13)
    ax.set_ylabel("EUR")
    _format_date_axis(ax)
    _format_eur_axis(ax, prefix="\u20ac")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig5_contributions_vs_value.png", dpi=180)
    plt.close(fig)
    print("  Saved fig5_contributions_vs_value.png")


# ══════════════════════════════════════════════════════════════════════════
# Claim validation
# ══════════════════════════════════════════════════════════════════════════


def validate_claims(
    indicators: dict[date, dict[str, bool]],
    baseline: IterationResult,
    strategy: IterationResult,
) -> None:
    """Print all numerical claims for cross-referencing with the paper."""
    b_final = float(baseline.final_value)
    s_final = float(strategy.final_value)
    delta = s_final - b_final

    # Composite fire days
    fire_dates = [
        d for d, ind in indicators.items() if sum(ind.values()) >= MIN_ACTIVE_INDICATORS
    ]

    # Compute contributions from calendar months
    # 2 PAC events per month, each €250, for each month in the range
    all_dates = [dr.date for dr in strategy.daily_values]
    first_month = all_dates[0].replace(day=1)
    last_month = all_dates[-1].replace(day=1)
    month_count = 0
    cur = first_month
    while cur <= last_month:
        month_count += 1
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    # Subtract 1 because the first month's PAC might not fire (start of sim)
    total_contributions = float(INITIAL_EUR) + (month_count - 1) * float(
        MONTHLY_PAC_EUR
    )

    # Max drawdowns
    b_max_dd = _max_drawdown([float(dr.total_value) for dr in baseline.daily_values])
    s_max_dd = _max_drawdown([float(dr.total_value) for dr in strategy.daily_values])

    # Hard trades (only hard_rebalance type, not PAC executions)
    hard_trades = sum(
        1 for t in strategy.trades if t.type == "hard_rebalance" and not t.skipped
    )

    # Tilted months — approximate from fire dates + recovery
    # Count months where composite was active or within recovery_days
    recovery_days = STRATEGY_PARAMS["recovery_days"]
    tilted_dates = set()
    for fd in fire_dates:
        for offset in range(recovery_days + 1):
            tilted_dates.add(fd + timedelta(days=offset))

    tilted_months = set()
    for d in tilted_dates:
        tilted_months.add((d.year, d.month))

    total_months = set()
    for d in all_dates:
        total_months.add((d.year, d.month))

    # Crisis episodes (distinct composite fire windows with 30+ day gaps)
    sorted_fires = sorted(fire_dates)
    episodes = 0
    last_ep_end: date | None = None
    for d in sorted_fires:
        if last_ep_end is None or (d - last_ep_end).days > 30:
            episodes += 1
        last_ep_end = d

    # FP analysis — composite days outside crisis windows
    fp_days = [d for d in fire_dates if not _in_crisis(d)]
    total_indicator_days = len(indicators)
    fp_rate = len(fp_days) / total_indicator_days * 100 if total_indicator_days else 0

    # Return on contributions
    b_roc = (b_final / total_contributions - 1) * 100
    s_roc = (s_final / total_contributions - 1) * 100
    delta_pp = s_roc - b_roc

    alpha_s = f"\u20ac{delta:,.0f}"
    tilted_s = f"{len(tilted_months)}/{len(total_months)}"

    print("\n" + "=" * 60)
    print("CLAIM VALIDATION")
    print("=" * 60)
    print(
        f"Total PAC contributions:     \u20ac{total_contributions:>10,.0f}"
        f"  (\u00a73.3, \u00a76.1)"
    )
    print(f"Baseline final value:        \u20ac{b_final:>10,.0f}")
    print(f"Strategy final value:        \u20ac{s_final:>10,.0f}")
    print(f"Alpha (absolute):            {alpha_s:>11s}" f"  (\u00a76.1)")
    print("Return on contributions:")
    print(f"  Baseline:                  {b_roc:>9.1f}%")
    print(f"  Strategy:                  {s_roc:>9.1f}%")
    print(f"  Delta:                     {delta_pp:>+9.1f}pp" f" (\u00a76.1)")
    print(f"Max drawdown baseline:       {b_max_dd:>9.1f}%" f"  (\u00a76.1)")
    print(f"Max drawdown strategy:       {s_max_dd:>9.1f}%" f"  (\u00a76.1)")
    print(f"Hard trades:                 {hard_trades:>9d}" f"    (\u00a76.1)")
    print(f"Tilted months:               {tilted_s:>9s}" f"    (\u00a76.1)")
    print(f"Crisis episodes detected:    {episodes:>9d}" f"    (\u00a72.4)")
    print(f"Composite fire days:         {len(fire_dates):>9d}" f"    (\u00a72.4)")
    print(f"False positive days:         {len(fp_days):>9d}")
    print(f"FP rate:                     {fp_rate:>9.1f}%" f"  (\u00a72.4)")
    print("=" * 60)

    # Per-crisis composite fire days
    print("\nPer-crisis composite fire days:")
    for name, (cs, ce) in CRISIS_WINDOWS.items():
        days_in_crisis = [d for d in fire_dates if cs <= d <= ce]
        print(f"  {name:>20s}: {len(days_in_crisis):>4d} days")

    # Per-indicator activation rates per crisis
    indicator_names = [
        "dd_depth",
        "dd_velocity",
        "divergence",
        "death_cross",
        "rs_breakout",
    ]
    print("\nIndicator activation rates per crisis (%):")
    header = f"{'Indicator':>15s}"
    for name in CRISIS_WINDOWS:
        header += f"  {name:>15s}"
    print(header)
    for ind in indicator_names:
        row = f"{ind:>15s}"
        for _, (cs, ce) in CRISIS_WINDOWS.items():
            crisis_days = [d for d in indicators if cs <= d <= ce]
            if not crisis_days:
                row += f"  {'N/A':>15s}"
            else:
                rate = (
                    100.0
                    * sum(1 for d in crisis_days if indicators[d].get(ind, False))
                    / len(crisis_days)
                )
                row += f"  {rate:>14.0f}%"

        print(row)


def _max_drawdown(values: list[float]) -> float:
    """Compute maximum drawdown in percent."""
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (v / peak - 1) * 100
        if dd < max_dd:
            max_dd = dd
    return max_dd


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Step 1/4: Loading price data...")
    price_data, asset_ticker_map = load_price_data()

    print("\nStep 2/4: Computing daily indicators (day-by-day, no look-ahead)...")
    indicators = compute_daily_indicators(price_data, asset_ticker_map)
    total_days = len(indicators)
    fire_days = sum(
        1 for ind in indicators.values() if sum(ind.values()) >= MIN_ACTIVE_INDICATORS
    )
    print(f"  {total_days} trading days analyzed, {fire_days} composite fire days")

    print("\nStep 3/4: Running backtester simulations...")
    baseline, strategy = run_simulations(price_data, asset_ticker_map)

    print("\nStep 4/4: Generating figures...")
    generate_fig1(price_data, asset_ticker_map, indicators)
    generate_fig2(indicators)
    generate_fig3(baseline, strategy)
    generate_fig4(float(baseline.final_value))
    generate_fig5(strategy)

    # Print claim validation
    validate_claims(indicators, baseline, strategy)

    print(f"\nAll figures saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
