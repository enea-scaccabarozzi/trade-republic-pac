from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action, PacAdjustment
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


class PacAlignmentParams(BaseModel):
    blend_factor: Decimal = Field(
        default=Decimal("1.0"),
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description=(
            "Fraction of PAC budget shifted toward underweight assets. "
            "0.0 = pure target-proportional (no shift), "
            "1.0 = all PAC toward most underweight assets."
        ),
    )
    min_eur_per_asset: Decimal = Field(
        default=Decimal("1.00"),
        ge=Decimal("1.00"),
        description="Minimum PAC allocation per asset in EUR (TR minimum is €1).",
    )


class PacAlignmentStrategy(BacktestStrategy[PacAlignmentParams]):
    """Shifts PAC volumes toward underweight assets on each PAC date.

    Uses a blended weighting: (1 - blend_factor) x target-proportional
    + blend_factor x underweight-proportional. At blend_factor=1.0,
    all PAC flows to the most underweight assets; at 0.0, volumes remain
    at target allocation.

    Never emits hard rebalance orders — pure PAC-adjustment strategy.

    Edge cases:
    - All assets overweight or at target: return None (no underweight present).
    - Single asset portfolio: returns volumes unchanged.
    - Rounding may cause total to deviate by ≤1 cent; corrected by adjusting
      the highest-volume asset.
    """

    name = "pac_alignment"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []

    def on_pac_date(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
        current_pac_volumes: dict[str, Decimal],
    ) -> PacAdjustment | None:
        """Adjust PAC volumes toward underweight assets using blend factor.

        Args:
            snapshot: Current portfolio state.
            report: Deviation analysis for the current portfolio.
            current_date: The PAC execution date.
            current_pac_volumes: Current PAC volumes per asset.

        Returns:
            PacAdjustment with rebalanced volumes, or None if no adjustment needed.
        """
        params = self._params

        # Step 1: total PAC budget
        total_pac = sum(current_pac_volumes.values())
        if total_pac == Decimal("0"):
            return None

        # Step 2: compute deficit (positive only for underweight assets)
        deficit: dict[str, Decimal] = {}
        for aid, dev in report.deviations.items():
            d = dev.target_pct - dev.actual_pct
            deficit[aid] = max(Decimal("0"), d)

        # Step 3: check if any deficit exists
        total_deficit = sum(deficit.values())
        if total_deficit == Decimal("0"):
            return None

        # Step 4: normalized target weights
        total_target = sum(dev.target_pct for dev in report.deviations.values())
        if total_target == Decimal("0"):
            return None
        target_w: dict[str, Decimal] = {
            aid: dev.target_pct / total_target
            for aid, dev in report.deviations.items()
        }

        # Step 5: normalized deficit weights
        deficit_w: dict[str, Decimal] = {
            aid: deficit[aid] / total_deficit for aid in deficit
        }

        # Step 6: blended weight
        blend = params.blend_factor
        blended_w: dict[str, Decimal] = {
            aid: (Decimal("1") - blend) * target_w.get(aid, Decimal("0"))
            + blend * deficit_w.get(aid, Decimal("0"))
            for aid in report.deviations
        }

        # Step 7: raw volumes
        raw_vol: dict[str, Decimal] = {
            aid: (total_pac * w).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for aid, w in blended_w.items()
        }

        # Step 8: apply minimum
        vol: dict[str, Decimal] = {
            aid: max(params.min_eur_per_asset, v) for aid, v in raw_vol.items()
        }

        # Step 9: re-normalize to preserve total_pac exactly
        raw_total = sum(vol.values())
        if raw_total != total_pac:
            adjustment = total_pac - raw_total
            # Apply adjustment to highest-volume asset to preserve all minimums
            max_aid = max(vol, key=lambda a: vol[a])
            vol[max_aid] = vol[max_aid] + adjustment

        return PacAdjustment(new_volumes=vol)
