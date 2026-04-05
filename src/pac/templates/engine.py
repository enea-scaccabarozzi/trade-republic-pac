from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import jinja2
from jinja2.sandbox import SandboxedEnvironment

from pac.delivery.base import RenderedMessage
from pac.models.signals import SignalSeverity
from pac.templates.adapters.base import FormatAdapter

# Reserved context names injected by the engine (adapter methods).
# Data keys must not shadow these.
_RESERVED_CONTEXT_KEYS = frozenset(
    {
        "bold",
        "italic",
        "code",
        "code_block",
        "link",
        "heading",
        "list_item",
        "separator",
        "escape",
        "emoji",
        "literal",
    }
)


class TemplateEngine:
    """Jinja2-based template engine with adapter-injected formatting.

    Loads templates from a directory (default: builtin/) and injects
    FormatAdapter methods as Jinja2 globals. Templates call bold(),
    escape(), etc. without knowing the target format.
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir is None:
            template_dir = Path(__file__).parent / "builtin"
        self._env = SandboxedEnvironment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            autoescape=False,
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.filters["datefmt"] = _datefmt_filter
        self._env.filters["numberfmt"] = _numberfmt_filter
        self._env.filters["pctfmt"] = _pctfmt_filter
        self._env.filters["eurfmt"] = _eurfmt_filter

    def render(
        self,
        template_name: str,
        data: dict[str, Any],
        adapter: FormatAdapter,
        *,
        signal_name: str,
        severity: SignalSeverity,
    ) -> RenderedMessage:
        """Render a template with the given data and format adapter.

        Args:
            template_name: Template file stem (e.g. 'threshold_alert').
                           '.j2' extension is appended automatically.
            data: Template context variables. Keys must not shadow reserved
                  adapter method names.
            adapter: FormatAdapter providing bold(), escape(), etc.
            signal_name: Signal name for the RenderedMessage.
            severity: Signal severity for the RenderedMessage.

        Returns:
            RenderedMessage ready for DeliveryChannel.send().

        Raises:
            ValueError: If any data key shadows a reserved context name.
        """
        collisions = _RESERVED_CONTEXT_KEYS & data.keys()
        if collisions:
            raise ValueError(
                f"Data keys shadow reserved context names: {sorted(collisions)}"
            )

        template = self._env.get_template(f"{template_name}.j2")

        globals_dict: dict[str, Any] = {
            "bold": adapter.bold,
            "italic": adapter.italic,
            "code": adapter.code,
            "code_block": adapter.code_block,
            "link": adapter.link,
            "heading": adapter.heading,
            "list_item": adapter.list_item,
            "separator": adapter.separator,
            "escape": adapter.escape,
            "emoji": adapter.emoji,
            "literal": adapter.literal,
        }

        content = template.render({**globals_dict, **data})

        return RenderedMessage(
            content=content,
            format=adapter.name,
            signal_name=signal_name,
            severity=severity,
        )

    def has_template(self, template_name: str) -> bool:
        """Check if a template exists."""
        try:
            self._env.get_template(f"{template_name}.j2")
        except jinja2.TemplateNotFound:
            return False
        return True


def _datefmt_filter(
    value: datetime,
    fmt: str = "%Y-%m-%d %H:%M UTC",
) -> str:
    """Format a datetime object."""
    return value.strftime(fmt)


def _numberfmt_filter(
    value: Decimal | float | int,
    decimals: int = 2,
) -> str:
    """Format a number to N decimal places."""
    return f"{float(value):.{decimals}f}"


def _pctfmt_filter(value: Decimal | float | int) -> str:
    """Format a value as a percentage string (e.g. '70.0%')."""
    return f"{float(value):.1f}%"


def _eurfmt_filter(value: Decimal | float | int) -> str:
    """Format a value as euros (e.g. '€500.00')."""
    return f"\u20ac{float(value):.2f}"
