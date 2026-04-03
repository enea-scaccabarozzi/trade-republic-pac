from __future__ import annotations

from decimal import Decimal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = {"env_prefix": "PAC_"}

    # Trade Republic credentials
    tr_phone_number: str = Field(description="TR phone number for login")
    tr_pin: str = Field(description="TR PIN for login")
    tr_cookies_path: str = Field(
        default="/tmp/tr_cookies",
        description="Path to TR session cookies",
    )

    # Telegram
    telegram_bot_token: str = Field(description="Telegram bot API token")
    telegram_chat_id: str = Field(description="Telegram chat ID for notifications")

    # Target allocation percentages (must sum to 100)
    target_stocks_pct: int = Field(default=70, ge=0, le=100)
    target_gold_pct: int = Field(default=15, ge=0, le=100)
    target_bonds_pct: int = Field(default=15, ge=0, le=100)

    # Asset ISINs
    isin_stocks: str = Field(default="IE00BK5BQT80", description="FTSE All-World ETF")
    isin_gold: str = Field(default="IE00B4ND3602", description="Physical Gold ETC")
    isin_bonds: str = Field(default="IE00B3F81409", description="Gov Bond ETF")

    # Rebalance thresholds
    deviation_warning_pct: Decimal = Field(
        default=Decimal("3.0"),
        description="Deviation % to trigger a warning signal",
    )
    deviation_critical_pct: Decimal = Field(
        default=Decimal("5.0"),
        description="Deviation % to trigger a critical signal",
    )
    cycle_inversion_min_pct: Decimal = Field(
        default=Decimal("2.0"),
        description="Min deviation % per side to flag a cycle inversion",
    )

    # PAC
    pac_monthly_budget: Decimal = Field(
        default=Decimal("500.00"),
        description="Monthly PAC investment budget in EUR",
    )
    pac_day_of_month: int = Field(
        default=14,
        ge=1,
        le=28,
        description="Day of month for PAC calculation",
    )

    # Webhook / serverless
    webhook_url: str = Field(
        default="",
        description="Public URL for Telegram webhook (e.g. https://my-service.run.app/webhook)",
    )
    webhook_secret: str = Field(
        description="Secret for X-Telegram-Bot-Api-Secret-Token header",
    )
    job_secret: str = Field(
        description="Secret token for X-Job-Secret header on Cloud Scheduler requests",
    )

    @model_validator(mode="after")
    def _check_allocation_sum(self) -> Settings:
        total = self.target_stocks_pct + self.target_gold_pct + self.target_bonds_pct
        if total != 100:
            msg = f"Target allocations must sum to 100, got {total}"
            raise ValueError(msg)
        return self
