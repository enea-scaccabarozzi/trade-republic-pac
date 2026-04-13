from __future__ import annotations

import importlib
import pkgutil
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel

from pac.analysis.deviation import DeviationReport, calculate_deviations
from pac.analysis.rebalance import PacPlan, compute_pac_plan
from pac.config import Settings
from pac.delivery.base import DeliveryChannel
from pac.delivery.discovery import discover_channels
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal
from pac.rules.discovery import discover_rules
from pac.rules.registry import SignalRegistry
from pac.templates.adapters.base import FormatAdapter
from pac.templates.engine import TemplateEngine
from pac.tr.client import tr_session

logger = structlog.get_logger()


class DispatchResult(BaseModel):
    """Result of a signal dispatch — returned to the HTTP adapter."""

    signal_name: str
    signal_count: int
    delivered: bool


class SignalNotFoundError(Exception):
    """Raised when a signal name is not in the config."""


class Orchestrator:
    """Framework-agnostic signal dispatch pipeline.

    Wires config → rules → templates → channels. No HTTP, no Starlette.
    Consumed by the HTTP adapter (app.py) and interactive channel handlers.
    """

    def __init__(
        self,
        settings: Settings,
        registry: SignalRegistry,
        channels: dict[str, DeliveryChannel[Any]],
        template_engine: TemplateEngine,
        adapters: dict[str, FormatAdapter],
        market_ctx_enabled: bool = False,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._channels = channels
        self._engine = template_engine
        self._adapters = adapters
        self._signal_map: dict[str, Any] = {sig.name: sig for sig in settings.signals}
        self._market_ctx_enabled = market_ctx_enabled
        self._ticker_map: dict[str, str] = {
            a.id: a.ticker for a in settings.assets if a.ticker
        }

    @classmethod
    def from_settings(cls, settings: Settings) -> Orchestrator:
        """Factory: discover rules + channels, wire everything from config.

        No network calls — only filesystem (config) and imports (discovery).
        """
        # 1. Discover and register rules
        rule_classes = discover_rules()
        registry = SignalRegistry()
        for rule_cls in rule_classes.values():
            registry.register(rule_cls)

        # 2. Discover channel classes and instantiate with typed config
        channel_classes = discover_channels()
        channels: dict[str, DeliveryChannel[Any]] = {}
        for ch_name, ch_raw_config in settings.channels.items():
            ch_type = ch_raw_config.get("type", ch_name)
            if ch_type not in channel_classes:
                msg = (
                    f"Channel '{ch_name}' references unknown type '{ch_type}'. "
                    f"Available: {sorted(channel_classes.keys())}"
                )
                raise ValueError(msg)
            ch_cls = channel_classes[ch_type]
            typed_config = ch_cls.config_model.model_validate(ch_raw_config)
            channels[ch_name] = ch_cls(typed_config)

        # 3. Build template engine (filesystem only)
        template_engine = TemplateEngine()

        # 4. Discover adapters from FormatAdapter subclasses
        # Uses __subclasses__() instead of a registry because adapters are
        # simple stateless singletons — a registry would add ceremony without
        # value. Importing the adapters package triggers subclass registration.
        adapters = _discover_adapters()

        # 5. Validate signal configs reference known rules + channels + templates
        for sig in settings.signals:
            if sig.rule not in registry:
                msg = f"Signal '{sig.name}' references unknown rule '{sig.rule}'"
                raise ValueError(msg)
            for ch in sig.channels:
                if ch not in channels:
                    msg = f"Signal '{sig.name}' references unknown channel '{ch}'"
                    raise ValueError(msg)
            if not template_engine.has_template(sig.template):
                msg = (
                    f"Signal '{sig.name}' references unknown template '{sig.template}'"
                )
                raise ValueError(msg)

        # 6. Cross-validate: each channel's supported_formats has an adapter
        for ch_name, channel in channels.items():
            for fmt in channel.supported_formats:
                if fmt not in adapters:
                    msg = (
                        f"Channel '{ch_name}' requires format '{fmt}' "
                        f"but no adapter found. "
                        f"Available: {sorted(adapters.keys())}"
                    )
                    raise ValueError(msg)

        # 7. Probe yfinance availability (no network calls)
        market_ctx_enabled = False
        try:
            importlib.import_module("yfinance")
            market_ctx_enabled = True
        except ImportError:
            pass

        return cls(
            settings=settings,
            registry=registry,
            channels=channels,
            template_engine=template_engine,
            adapters=adapters,
            market_ctx_enabled=market_ctx_enabled,
        )

    async def start(self) -> None:
        """Lifecycle: inject self into channels, then start them."""
        for name, channel in self._channels.items():
            logger.info("channel_starting", channel=name)
            await channel.set_orchestrator(self)
            await channel.start()
            logger.info("channel_started", channel=name)

    async def stop(self) -> None:
        """Lifecycle: shut down all channels."""
        for name, channel in self._channels.items():
            logger.info("channel_stopping", channel=name)
            await channel.stop()
            logger.info("channel_stopped", channel=name)

    def _build_market_ctx(self) -> Any:
        """Build a LiveMarketContext if yfinance is available, else None."""
        if not self._market_ctx_enabled:
            return None
        from pac.live_market_context import LiveMarketContext

        return LiveMarketContext(ticker_map=self._ticker_map)

    async def dispatch_signal(self, signal_name: str) -> DispatchResult:
        """Full pipeline: evaluate signal → render template → send.

        Used by the cron HTTP endpoint. Fetches portfolio, evaluates
        the signal's rule, renders the template, and sends to all
        configured channels.

        Partial delivery failure is logged but not retried.

        Raises:
            SignalNotFoundError: If signal_name is not in config.
        """
        sig_config = self._signal_map.get(signal_name)
        if sig_config is None:
            raise SignalNotFoundError(signal_name)

        # 1. Fetch portfolio
        async with tr_session(self._settings) as tr:
            snapshot = await tr.get_portfolio()

        # 2. Compute deviations
        report = calculate_deviations(snapshot, self._settings)

        # 3. Evaluate rule with typed params
        market_ctx = self._build_market_ctx()
        signals = self._registry.evaluate_signal(
            sig_config.rule,
            sig_config.params,
            report,
            snapshot,
            market_ctx=market_ctx,
        )

        if not signals:
            return DispatchResult(
                signal_name=signal_name,
                signal_count=0,
                delivered=False,
            )

        # 4. Build template data via rule's classmethod
        rule_cls = self._registry.get_rule(sig_config.rule)
        data = rule_cls.build_template_data(signals, report, snapshot)

        # 5. Render + send for each channel's preferred format
        for ch_name in sig_config.channels:
            channel = self._channels[ch_name]
            fmt = channel.supported_formats[0]
            adapter = self._adapters[fmt]
            rendered = self._engine.render(
                sig_config.template,
                data,
                adapter,
                signal_name=signal_name,
                severity=signals[0].severity,
            )
            try:
                await channel.send(rendered)
            except Exception:
                # Partial delivery failure: signal was evaluated successfully,
                # so we log and continue to remaining channels.
                logger.exception(
                    "channel_send_failed",
                    channel=ch_name,
                    signal=signal_name,
                )

        return DispatchResult(
            signal_name=signal_name,
            signal_count=len(signals),
            delivered=True,
        )

    async def evaluate_signal(self, signal_name: str) -> list[Signal]:
        """Evaluate a signal and return results WITHOUT sending.

        Used by interactive handlers that manage their own response.

        Raises:
            SignalNotFoundError: If signal_name is not in config.
        """
        sig_config = self._signal_map.get(signal_name)
        if sig_config is None:
            raise SignalNotFoundError(signal_name)

        async with tr_session(self._settings) as tr:
            snapshot = await tr.get_portfolio()

        report = calculate_deviations(snapshot, self._settings)
        market_ctx = self._build_market_ctx()
        return self._registry.evaluate_signal(
            sig_config.rule,
            sig_config.params,
            report,
            snapshot,
            market_ctx=market_ctx,
        )

    async def evaluate_all_signals(
        self,
    ) -> tuple[list[Signal], PortfolioSnapshot, DeviationReport]:
        """Evaluate ALL configured signals and return results.

        Used by interactive handlers (e.g., Telegram /rebalance) that
        manage their own response rendering.
        """
        async with tr_session(self._settings) as tr:
            snapshot = await tr.get_portfolio()

        report = calculate_deviations(snapshot, self._settings)
        market_ctx = self._build_market_ctx()
        signals = self._registry.evaluate_all(report, snapshot, market_ctx=market_ctx)
        return signals, snapshot, report

    async def get_portfolio_status(
        self,
    ) -> tuple[PortfolioSnapshot, DeviationReport]:
        """Fetch portfolio and compute deviations.

        Used by /status command.
        """
        async with tr_session(self._settings) as tr:
            snapshot = await tr.get_portfolio()
        report = calculate_deviations(snapshot, self._settings)
        return snapshot, report

    async def compute_pac_plan(self, signal_name: str) -> PacPlan:
        """Compute PAC redistribution plan from signal config params.

        Extracts monthly_budget from the signal's params.
        Used by /redistribute command.

        Raises:
            SignalNotFoundError: If signal_name is not in config.
        """
        sig_config = self._signal_map.get(signal_name)
        if sig_config is None:
            raise SignalNotFoundError(signal_name)

        async with tr_session(self._settings) as tr:
            snapshot = await tr.get_portfolio()

        targets = self._settings.target_allocations
        asset_names = {a.id: a.name for a in self._settings.assets}
        budget = sig_config.params.get("monthly_budget", 500.0)

        return compute_pac_plan(snapshot, targets, asset_names, Decimal(str(budget)))

    def get_channel(self, name: str) -> DeliveryChannel[Any]:
        """Look up a channel instance by name.

        Raises:
            KeyError: If name is not registered.
        """
        return self._channels[name]

    @property
    def settings(self) -> Settings:
        """Access the app settings (for auth checks in HTTP adapter)."""
        return self._settings

    @property
    def registry(self) -> SignalRegistry:
        """Access the signal registry (for interactive handlers)."""
        return self._registry

    @property
    def template_engine(self) -> TemplateEngine:
        """Access the template engine (for interactive handlers)."""
        return self._engine

    @property
    def signal_names(self) -> list[str]:
        """All configured signal names."""
        return list(self._signal_map.keys())


def _discover_adapters() -> dict[str, FormatAdapter]:
    """Build adapter lookup from all FormatAdapter subclasses.

    Imports all modules in pac.templates.adapters to trigger
    subclass registration, then collects instances keyed by name.
    """
    import pac.templates.adapters as pkg

    for info in pkgutil.iter_modules(pkg.__path__, prefix=f"{pkg.__name__}."):
        # Skip base.py — it defines the ABC itself, not a concrete adapter.
        if not info.name.endswith(".base"):
            importlib.import_module(info.name)

    return {cls().name: cls() for cls in FormatAdapter.__subclasses__()}  # type: ignore[abstract]
