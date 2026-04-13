from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.analysis.rebalance import compute_pac_plan
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal, SignalSeverity
from pac.rules.base import SignalRule

if TYPE_CHECKING:
    from pac.market_context import MarketContext


class PacPlanParams(BaseModel):
    """Parameters for the PAC plan computation rule."""

    monthly_budget: Decimal = Field(default=Decimal("500.00"), gt=0)
    day_of_month: int = Field(default=16, ge=1, le=28)


class PacPlanRule(SignalRule[PacPlanParams]):
    """Computes monthly PAC allocation plan and emits a summary signal."""

    @property
    def name(self) -> str:
        return "pac_plan"

    def evaluate(
        self,
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
        params: PacPlanParams,
        market_ctx: MarketContext | None = None,
    ) -> list[Signal]:
        """Compute a monthly PAC allocation plan and emit a summary signal."""
        targets = {aid: dev.target_pct for aid, dev in report.deviations.items()}
        asset_names = {aid: dev.name for aid, dev in report.deviations.items()}

        plan = compute_pac_plan(
            snapshot=snapshot,
            targets=targets,
            asset_names=asset_names,
            total_budget=params.monthly_budget,
        )

        alloc_summary = "; ".join(
            f"{a.name}: €{a.amount:.2f} ({a.pct_of_budget:.0f}%)"
            for a in plan.allocations.values()
        )
        return [
            Signal(
                name=self.name,
                severity=SignalSeverity.INFO,
                message=(
                    f"Monthly PAC plan (€{params.monthly_budget:.2f}): {alloc_summary}"
                ),
                triggered_at=report.timestamp,
                metadata={
                    "monthly_budget": float(params.monthly_budget),
                    "day_of_month": params.day_of_month,
                    "allocations": {
                        aid: {
                            "name": a.name,
                            "amount": float(a.amount),
                            "pct_of_budget": float(a.pct_of_budget),
                        }
                        for aid, a in plan.allocations.items()
                    },
                },
            )
        ]

    @classmethod
    def build_template_data(
        cls,
        signals: list[Signal],
        report: DeviationReport,
        snapshot: PortfolioSnapshot,
    ) -> dict[str, Any]:
        """Recompute PAC plan for template rendering."""
        signal = signals[0]
        budget = Decimal(str(signal.metadata["monthly_budget"]))
        targets = {aid: dev.target_pct for aid, dev in report.deviations.items()}
        asset_names = {aid: dev.name for aid, dev in report.deviations.items()}
        plan = compute_pac_plan(snapshot, targets, asset_names, budget)
        return {"plan": plan}
