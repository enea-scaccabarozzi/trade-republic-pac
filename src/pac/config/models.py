from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AppConfig(BaseModel):
    """Application-level settings (log level, dev mode, port, job secret)."""

    log_level: str = "INFO"
    dev_mode: bool = False
    port: int = 8080
    job_secret: str = Field(
        description="HMAC secret for X-Job-Secret header",
    )


class BrokerConfig(BaseModel):
    """Broker connection credentials.

    ``type`` field enables future broker implementations.
    """

    type: str = "trade_republic"
    phone_number: str
    pin: str
    cookies_path: str = "/tmp/tr_cookies"


class ProxySpec(BaseModel):
    """Single proxy segment in a chain."""

    ticker: str = Field(description="Yahoo Finance ticker for this proxy segment")
    end: date = Field(description="Last date (inclusive) to use this proxy's data")
    currency: str | None = Field(
        default=None,
        description=(
            "ISO 4217 currency code (e.g. 'USD', 'GBP'). "
            "If set, FX conversion to EUR is applied."
        ),
    )


class AssetConfig(BaseModel):
    """Single asset definition for portfolio tracking."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    isin: str = Field(pattern=r"^[A-Z]{2}[A-Z0-9]{10}$")
    target_pct: Decimal = Field(ge=0, le=100)
    ticker: str | None = Field(
        default=None,
        description=(
            "Yahoo Finance ticker symbol (e.g. 'EUNL.DE'). Required for backtesting."
        ),
    )
    proxy_ticker: str | None = Field(
        default=None,
        description="Proxy ticker for backtesting before the primary ETF existed",
    )
    proxy_end: date | None = Field(
        default=None,
        description="Last date to use proxy data (primary takes over after this)",
    )
    proxy_chain: list[ProxySpec] = Field(
        default_factory=list,
        description=(
            "Ordered list of proxy segments (oldest first). "
            "Each covers [start, spec.end]; primary ticker takes over after "
            "last spec.end."
        ),
    )
    currency: str | None = Field(
        default=None,
        description=(
            "Currency of primary ticker. If set and not EUR, FX conversion applied."
        ),
    )

    @model_validator(mode="after")
    def _check_proxy_fields(self) -> AssetConfig:
        if self.proxy_end and not self.proxy_ticker:
            msg = f"Asset '{self.id}': proxy_end requires proxy_ticker"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _migrate_legacy_proxy(self) -> AssetConfig:
        """Convert legacy proxy_ticker/proxy_end to proxy_chain."""
        if self.proxy_ticker and self.proxy_end and not self.proxy_chain:
            self.proxy_chain = [ProxySpec(ticker=self.proxy_ticker, end=self.proxy_end)]
        return self

    @model_validator(mode="after")
    def _check_proxy_chain_order(self) -> AssetConfig:
        for i in range(1, len(self.proxy_chain)):
            if self.proxy_chain[i].end <= self.proxy_chain[i - 1].end:
                msg = (
                    f"Asset '{self.id}': proxy_chain must be ordered "
                    f"chronologically. Segment {i} end "
                    f"({self.proxy_chain[i].end}) <= segment {i - 1} end "
                    f"({self.proxy_chain[i - 1].end})"
                )
                raise ValueError(msg)
        return self


class SignalConfig(BaseModel):
    """Signal rule wiring: maps a rule + params + template + channels."""

    name: str
    rule: str
    schedule: str
    channels: list[str]
    params: dict[str, Any] = Field(default_factory=dict)
    template: str


class Settings(BaseModel):
    """Top-level config loaded from pac.yaml."""

    version: int = Field(description="Config schema version")
    app: AppConfig
    broker: BrokerConfig
    assets: list[AssetConfig]
    channels: dict[str, dict[str, Any]] = Field(default_factory=dict)
    signals: list[SignalConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_allocation_sum(self) -> Settings:
        total = sum(a.target_pct for a in self.assets)
        if total != 100:
            msg = f"Asset target_pct must sum to 100, got {total}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_unique_asset_ids(self) -> Settings:
        ids = [a.id for a in self.assets]
        if len(ids) != len(set(ids)):
            msg = "Asset IDs must be unique"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_signal_channels_exist(self) -> Settings:
        channel_keys = set(self.channels.keys())
        for sig in self.signals:
            for ch in sig.channels:
                if ch not in channel_keys:
                    msg = f"Signal '{sig.name}' references unknown channel '{ch}'"
                    raise ValueError(msg)
        return self

    @property
    def asset_map(self) -> dict[str, AssetConfig]:
        """Lookup asset config by ID."""
        return {a.id: a for a in self.assets}

    @property
    def isin_to_asset_id(self) -> dict[str, str]:
        """Reverse lookup: ISIN -> asset ID."""
        return {a.isin: a.id for a in self.assets}

    @property
    def target_allocations(self) -> dict[str, Decimal]:
        """Asset ID -> target percentage."""
        return {a.id: a.target_pct for a in self.assets}
