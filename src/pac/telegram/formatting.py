from __future__ import annotations

from decimal import Decimal

from pac.analysis.deviation import DeviationReport
from pac.analysis.rebalance import PacPlan
from pac.models.portfolio import AssetClass, PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity

_SEVERITY_EMOJI: dict[SignalSeverity, str] = {
    SignalSeverity.INFO: "ℹ️",  # noqa: RUF001
    SignalSeverity.WARNING: "⚠️",
    SignalSeverity.CRITICAL: "🚨",
}

_ASSET_LABEL: dict[AssetClass, str] = {
    AssetClass.STOCKS: "Stocks",
    AssetClass.GOLD: "Gold",
    AssetClass.BONDS: "Bonds",
}

_SPECIAL_CHARS = "_*[]()~`>#+-=|{}.!"


def _escape(text: str) -> str:
    """Escape MarkdownV2 special characters in user-facing text.

    Backslash is processed first to avoid double-escaping.
    """
    text = text.replace("\\", "\\\\")
    result: list[str] = []
    for ch in text:
        if ch in _SPECIAL_CHARS:
            result.append(f"\\{ch}")
        else:
            result.append(ch)
    return "".join(result)


def _fmt_pct(value: Decimal) -> str:
    """Format a Decimal percentage, escaped for MarkdownV2."""
    return _escape(f"{value:.1f}%")


def _fmt_eur(value: Decimal) -> str:
    """Format a Decimal euro amount, escaped for MarkdownV2."""
    return _escape(f"€{value:.2f}")


def format_signal_alert(signal: Signal) -> str:
    """Format a single signal as a MarkdownV2 message."""
    emoji = _SEVERITY_EMOJI[signal.severity]
    severity_upper = _escape(signal.severity.value.upper())
    name = _escape(signal.name)
    message = _escape(signal.message)
    ts = _escape(signal.triggered_at.strftime("%Y-%m-%d %H:%M UTC"))

    lines = [
        f"{emoji} *Signal: {name}*",
        f"Severity: `{severity_upper}`",
        "",
        message,
        "",
        f"_{ts}_",
    ]
    return "\n".join(lines)


def format_signal_alerts(signals: list[Signal]) -> str:
    """Format multiple signals into a single MarkdownV2 message."""
    if not signals:
        return _escape("No active signals.")
    return "\n\n———\n\n".join(format_signal_alert(s) for s in signals)


def format_portfolio_status(
    snapshot: PortfolioSnapshot,
    report: DeviationReport,
) -> str:
    """Format portfolio status as a MarkdownV2 message."""
    lines: list[str] = ["*Portfolio Status*", ""]

    for ac in AssetClass:
        dev = report.deviations[ac]
        label = _escape(_ASSET_LABEL[ac])
        actual = _fmt_pct(dev.actual_pct)
        target = _fmt_pct(dev.target_pct)
        deviation = _fmt_pct(dev.deviation_pct)
        sign = "\\+" if dev.deviation_pct > 0 else ""
        emoji = _SEVERITY_EMOJI[dev.severity]
        lines.append(f"{emoji} *{label}*: {actual} / {target} \\({sign}{deviation}\\)")

    lines.append("")
    lines.append(f"Cash: {_fmt_eur(snapshot.cash)}")
    lines.append(f"Total: {_fmt_eur(snapshot.total_value)}")

    return "\n".join(lines)


def format_pac_plan(plan: PacPlan) -> str:
    """Format a PAC redistribution plan as a MarkdownV2 message."""
    lines: list[str] = [
        "*Monthly PAC Redistribution*",
        "",
        f"Budget: {_fmt_eur(plan.total_budget)}",
        "",
    ]

    for ac in AssetClass:
        alloc = plan.allocations[ac]
        label = _escape(_ASSET_LABEL[ac])
        amount = _fmt_eur(alloc.amount)
        pct = _fmt_pct(alloc.pct_of_budget)
        current = _fmt_pct(alloc.current_pct)
        target = _fmt_pct(alloc.target_pct)
        lines.append(f"• *{label}*: {amount} \\({pct}\\)")
        lines.append(f"  Current: {current} → Target: {target}")

    return "\n".join(lines)
