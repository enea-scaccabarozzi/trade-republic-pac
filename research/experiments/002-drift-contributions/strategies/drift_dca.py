"""DriftDCA strategy — adjusts PAC volumes based on allocation drift.

Redistributes the same total monthly contribution toward underweight
assets, using one of three formulas: proportional, threshold, or stepped.
Never sells; never adds extra capital.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field

from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action, PacAdjustment
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.portfolio import PortfolioSnapshot
from pac.models.signals import Signal


class DriftDCAParams(BaseModel, frozen=True):
    """Parameters for the DriftDCA strategy.

    Args:
        adjustment_formula: Which redistribution formula to apply.
        threshold_pct: Minimum |drift| to trigger an adjustment
            (used by threshold and stepped formulas).
        max_tilt_pct: Maximum deviation from target weights, as a
            fraction of the available range (0.0 = baseline / no tilt,
            1.0 = full tilt toward the most underweight asset).
    """

    adjustment_formula: Literal["proportional", "threshold", "stepped"] = "proportional"
    threshold_pct: float = Field(default=3.0, ge=0.0)
    max_tilt_pct: float = Field(default=0.5, ge=0.0, le=1.0)


class DriftDCAStrategy(BacktestStrategy[DriftDCAParams]):
    """Steers PAC contributions toward underweight assets based on drift.

    On each PAC date, computes the current allocation drift from the
    ``DeviationReport`` and tilts the contribution split in the direction
    of the most underweight assets. The total budget is always preserved —
    only the per-asset split changes.

    Three formulas control when and how strongly the tilt is applied:
    - **proportional**: always active; tilt proportional to drift magnitude.
    - **threshold**: tilt only when any asset's |drift| >= threshold_pct.
    - **stepped**: discrete 0 / 50% / 100% tilt based on max |drift|.

    Never emits hard rebalance orders. Returns None (no change) when:
    - max_tilt_pct == 0.0 (baseline behaviour requested), or
    - the formula conditions are not met.
    """

    name = "drift_dca"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        """Return no actions — this is a PAC-only strategy."""
        return []

    def on_pac_date(
        self,
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
        current_pac_volumes: dict[str, Decimal],
    ) -> PacAdjustment | None:
        """Compute drift-adjusted PAC volumes.

        Args:
            snapshot: Current portfolio state.
            report: Deviation analysis for the current portfolio.
            current_date: The PAC execution date.
            current_pac_volumes: Current PAC volumes per asset in EUR.

        Returns:
            PacAdjustment with redistributed volumes, or None to keep the
            current allocation unchanged.
        """
        params = self._params

        # No tilt requested → behave identically to baseline.
        if params.max_tilt_pct == 0.0:
            return None

        total_budget = sum(current_pac_volumes.values())
        if total_budget == Decimal("0"):
            return None

        # Collect drift values (actual - target; negative = underweight).
        drift: dict[str, Decimal] = {
            aid: dev.deviation_pct for aid, dev in report.deviations.items()
        }
        max_abs_drift = max(abs(d) for d in drift.values()) if drift else Decimal("0")

        # Determine tilt_factor from the chosen formula.
        tilt_factor = self._compute_tilt_factor(
            formula=params.adjustment_formula,
            max_abs_drift=max_abs_drift,
            threshold=Decimal(str(params.threshold_pct)),
            max_tilt=Decimal(str(params.max_tilt_pct)),
        )

        if tilt_factor == Decimal("0"):
            # Formula said "don't adjust".
            return None

        new_volumes = self._compute_volumes(
            drift=drift,
            report=report,
            total_budget=total_budget,
            tilt_factor=tilt_factor,
        )

        self._emit_event(
            event_type="drift_adjust",
            current_date=current_date,
            details={
                "formula": params.adjustment_formula,
                "tilt_factor": float(tilt_factor),
                "max_abs_drift_pct": float(max_abs_drift),
                "new_volumes": {k: float(v) for k, v in new_volumes.items()},
            },
        )

        return PacAdjustment(new_volumes=new_volumes)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_tilt_factor(
        formula: str,
        max_abs_drift: Decimal,
        threshold: Decimal,
        max_tilt: Decimal,
    ) -> Decimal:
        """Map formula + drift magnitude to a tilt_factor in [0, max_tilt].

        Args:
            formula: One of "proportional", "threshold", "stepped".
            max_abs_drift: Largest absolute drift across all assets.
            threshold: Minimum drift to trigger (threshold/stepped only).
            max_tilt: Upper bound on tilt (fraction, 0–1).

        Returns:
            Tilt factor in [0, max_tilt]. 0 means "no adjustment".
        """
        if formula == "proportional":
            # Always active; scale linearly with max drift up to max_tilt.
            # The scaling factor maps max_abs_drift onto [0, max_tilt].
            # Since drift can theoretically reach 100pp, we cap at max_tilt.
            return min(max_tilt, max_tilt * max_abs_drift / Decimal("100"))

        if formula == "threshold":
            if max_abs_drift < threshold:
                return Decimal("0")
            return min(max_tilt, max_tilt * max_abs_drift / Decimal("100"))

        # stepped
        if max_abs_drift < threshold:
            return Decimal("0")
        if max_abs_drift < threshold * Decimal("2"):
            return max_tilt * Decimal("0.5")
        return max_tilt

    @staticmethod
    def _compute_volumes(
        drift: dict[str, Decimal],
        report: DeviationReport,
        total_budget: Decimal,
        tilt_factor: Decimal,
    ) -> dict[str, Decimal]:
        """Compute new per-asset volumes from drift and tilt_factor.

        Algorithm:
        1. Start from target weights (the stable anchor).
        2. Compute the underweight amount per asset (clamped at 0 for
           overweight assets — we never reduce allocations below 0).
        3. Normalize underweight amounts to produce a "correction weight".
        4. Blend: final_weight = target_weight + tilt_factor * correction_weight.
           The correction shifts weight *toward* underweight assets.
        5. Clamp all weights to >= 0.
        6. Normalise so weights sum to 100%.
        7. Convert to EUR volumes; correct rounding drift on the largest asset.

        Args:
            drift: Per-asset drift (actual - target); negative = underweight.
            report: Deviation report (used for target_pct values).
            total_budget: Total EUR to distribute.
            tilt_factor: Scaling factor in (0, max_tilt_pct].

        Returns:
            New per-asset EUR volumes summing exactly to total_budget.
        """
        asset_ids = list(report.deviations.keys())

        # Step 1: target weights as percentages (sum ≈ 100).
        target_w: dict[str, Decimal] = {
            aid: report.deviations[aid].target_pct for aid in asset_ids
        }
        total_target = sum(target_w.values())
        if total_target == Decimal("0"):
            return {}

        # Normalise to fractions summing to 1.
        target_frac: dict[str, Decimal] = {
            aid: target_w[aid] / total_target for aid in asset_ids
        }

        # Step 2: underweight amount = max(0, -drift) for each asset.
        underweight: dict[str, Decimal] = {
            aid: max(Decimal("0"), -drift.get(aid, Decimal("0"))) for aid in asset_ids
        }
        total_underweight = sum(underweight.values())

        # Step 3: correction fractions (zero-vector if nothing is underweight).
        if total_underweight == Decimal("0"):
            correction_frac: dict[str, Decimal] = {aid: Decimal("0") for aid in asset_ids}
        else:
            correction_frac = {
                aid: underweight[aid] / total_underweight for aid in asset_ids
            }

        # Step 4: blended fractions.
        # correction_frac already sums to 1 and target_frac sums to 1, so
        # blended sums to (1 - tilt_factor) + tilt_factor = 1 before clamping.
        blended: dict[str, Decimal] = {
            aid: (Decimal("1") - tilt_factor) * target_frac[aid]
            + tilt_factor * correction_frac[aid]
            for aid in asset_ids
        }

        # Step 5: clamp negatives.
        blended = {aid: max(Decimal("0"), v) for aid, v in blended.items()}

        # Step 6: re-normalise.
        total_blended = sum(blended.values())
        if total_blended == Decimal("0"):
            # Fallback: equal split.
            n = Decimal(str(len(asset_ids)))
            normalised: dict[str, Decimal] = {aid: Decimal("1") / n for aid in asset_ids}
        else:
            normalised = {aid: v / total_blended for aid, v in blended.items()}

        # Step 7: convert to EUR, round to cents.
        volumes: dict[str, Decimal] = {
            aid: (total_budget * normalised[aid]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            for aid in asset_ids
        }

        # Correct rounding drift on the largest-volume asset.
        actual_total = sum(volumes.values())
        if actual_total != total_budget:
            max_aid = max(volumes, key=lambda a: volumes[a])
            volumes[max_aid] = volumes[max_aid] + (total_budget - actual_total)

        return volumes
