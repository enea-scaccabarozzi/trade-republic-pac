from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

__all__ = [
    "AssetTaxMeta",
    "ItalianTaxRegime",
    "NoTaxRegime",
    "TaxRegime",
    "TaxResult",
    "resolve_tax_regime",
]

_CENTS = Decimal("0.01")


class AssetTaxMeta(BaseModel, frozen=True):
    """Tax-relevant metadata for a single asset.

    Attributes:
        government_bond: Whether this asset is a government bond.
            Some tax regimes apply a reduced withholding rate to government
            bonds (e.g. Italy's 12.5% vs 26%).
    """

    government_bond: bool = False


class TaxResult(BaseModel, frozen=True):
    """Outcome of a single tax computation for one disposal event.

    Attributes:
        tax_owed: Monetary tax to be deducted from cash proceeds.
        loss_recorded: Capital loss to carry forward (zero when gain).
        effective_rate: tax_owed / gain as a fraction; zero when no gain.
    """

    tax_owed: Decimal
    loss_recorded: Decimal
    effective_rate: Decimal


class TaxRegime(ABC):
    """Abstract base for pluggable tax regimes.

    Implementations are injected into ``SimulatedPortfolio`` via DI.
    Each regime is responsible for computing tax on a single disposal
    event and for maintaining any carry-forward state (e.g. loss offsets).

    The ``reset()`` method is called before every Monte Carlo iteration
    so that carry-forward state does not leak between runs.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this tax regime."""
        ...

    @abstractmethod
    def compute_tax(
        self,
        proceeds: Decimal,
        cost_basis: Decimal,
        asset_meta: AssetTaxMeta,
        current_year: int | None = None,
    ) -> TaxResult:
        """Compute tax owed on a single disposal event.

        Args:
            proceeds: Total sale proceeds (shares * price).
            cost_basis: Original acquisition cost for the disposed shares.
            asset_meta: Tax-relevant metadata for the disposed asset.
            current_year: Calendar year of the disposal; used by regimes
                that apply annual loss-offset limits. ``None`` means the
                regime should not apply year-based restrictions.

        Returns:
            A ``TaxResult`` describing tax owed and any loss to carry forward.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset per-iteration carry-forward state.

        Called by the simulator before each Monte Carlo iteration to ensure
        accumulated losses do not leak between independent runs.
        """
        ...


class NoTaxRegime(TaxRegime):
    """Tax regime that applies zero tax — the opt-out default.

    Use this when the backtester is run without tax modelling, preserving
    pre-tax behaviour for performance comparison baselines.
    """

    @property
    def name(self) -> str:
        return "none"

    def compute_tax(
        self,
        proceeds: Decimal,
        cost_basis: Decimal,
        asset_meta: AssetTaxMeta,
        current_year: int | None = None,
    ) -> TaxResult:
        """Return a zero-tax result regardless of gain or loss.

        Args:
            proceeds: Total sale proceeds.
            cost_basis: Original acquisition cost.
            asset_meta: Asset metadata (unused).
            current_year: Calendar year (unused).

        Returns:
            A ``TaxResult`` with all fields set to zero.
        """
        return TaxResult(
            tax_owed=Decimal("0"),
            loss_recorded=Decimal("0"),
            effective_rate=Decimal("0"),
        )

    def reset(self) -> None:
        """No-op — this regime carries no state between iterations."""


class ItalianTaxRegime(TaxRegime):
    """Italian capital-gains tax regime with FIFO loss carryforward.

    Applies a 26% flat rate on capital gains and a reduced 12.5% rate on
    government bonds. Realised losses are stored in an annual ledger and
    offset future gains in FIFO order. Losses expire after
    ``loss_carryforward_years`` fiscal years (default 4, per Italian tax law).

    The loss ledger is keyed by the fiscal year of the disposal so that
    the simulator can call ``reset()`` between Monte Carlo iterations
    without mixing runs.

    Args:
        default_rate: Withholding rate applied to ordinary capital gains.
            Defaults to ``Decimal("0.26")`` (26 %).
        government_bond_rate: Reduced rate applied when ``asset_meta.government_bond``
            is ``True``. Defaults to ``Decimal("0.125")`` (12.5 %).
        loss_carryforward_years: Number of fiscal years a recorded loss
            remains eligible to offset gains. Defaults to ``4``.
    """

    def __init__(
        self,
        default_rate: Decimal = Decimal("0.26"),
        government_bond_rate: Decimal = Decimal("0.125"),
        loss_carryforward_years: int = 4,
    ) -> None:
        self._default_rate = default_rate
        self._government_bond_rate = government_bond_rate
        self._loss_carryforward_years = loss_carryforward_years
        # ledger: fiscal_year -> remaining loss available for offset
        self._loss_ledger: dict[int, Decimal] = {}

    @property
    def name(self) -> str:
        return "italian"

    def compute_tax(
        self,
        proceeds: Decimal,
        cost_basis: Decimal,
        asset_meta: AssetTaxMeta,
        current_year: int | None = None,
    ) -> TaxResult:
        """Compute Italian capital-gains tax with FIFO loss offset.

        On a loss, the absolute loss amount is stored in the ledger keyed by
        ``current_year`` and zero tax is returned. On a gain, prior losses are
        consumed oldest-first (FIFO), skipping those that have expired, until the
        gain is fully offset or the ledger is exhausted. Tax is then calculated
        on the remaining taxable gain.

        Args:
            proceeds: Total sale proceeds (shares * price).
            cost_basis: Original acquisition cost for the disposed shares.
            asset_meta: Tax-relevant metadata; ``government_bond=True`` selects
                the reduced 12.5% rate.
            current_year: Calendar year of the disposal, used to key new losses
                and to check expiry of existing losses. When ``None`` no loss
                tracking is performed.

        Returns:
            A ``TaxResult`` with ``tax_owed`` rounded to cents,
            ``loss_recorded`` for the current disposal, and ``effective_rate``
            as ``tax_owed / gain`` (zero when gain is zero or negative).
        """
        gain = proceeds - cost_basis

        if gain <= Decimal("0"):
            loss = -gain
            if current_year is not None and loss > Decimal("0"):
                self._loss_ledger[current_year] = (
                    self._loss_ledger.get(current_year, Decimal("0")) + loss
                )
            return TaxResult(
                tax_owed=Decimal("0"),
                loss_recorded=loss,
                effective_rate=Decimal("0"),
            )

        # Apply FIFO loss offset for positive gains
        taxable_gain = gain
        if current_year is not None:
            for year in sorted(self._loss_ledger):
                # Skip expired losses
                if current_year - year > self._loss_carryforward_years:
                    continue
                if taxable_gain <= Decimal("0"):
                    break
                available = self._loss_ledger[year]
                consumed = min(available, taxable_gain)
                taxable_gain -= consumed
                remaining = available - consumed
                if remaining == Decimal("0"):
                    del self._loss_ledger[year]
                else:
                    self._loss_ledger[year] = remaining

        rate = (
            self._government_bond_rate
            if asset_meta.government_bond
            else self._default_rate
        )
        tax_owed = (taxable_gain * rate).quantize(_CENTS)
        effective_rate = (tax_owed / gain) if gain else Decimal("0")

        return TaxResult(
            tax_owed=tax_owed,
            loss_recorded=Decimal("0"),
            effective_rate=effective_rate,
        )

    def reset(self) -> None:
        """Clear the loss ledger.

        Called by the simulator before each Monte Carlo iteration so that
        losses accumulated during one run do not carry over to the next.
        """
        self._loss_ledger.clear()


_TAX_REGIMES: dict[str, type[TaxRegime]] = {
    "none": NoTaxRegime,
    "italian": ItalianTaxRegime,
}


def resolve_tax_regime(
    name: str,
    params: dict[str, Any],
) -> TaxRegime:
    """Resolve a tax regime by name with optional configuration parameters.

    Args:
        name: Registered regime name (e.g. ``"italian"``, ``"none"``).
        params: Regime-specific parameters. For ``"italian"``: supports
            ``default_rate`` (float), ``government_bond_rate`` (float), and
            ``loss_carryforward_years`` (int). Unused for ``"none"``.

    Returns:
        A configured ``TaxRegime`` instance ready for injection.

    Raises:
        ValueError: If ``name`` is not in the registry.
    """
    cls = _TAX_REGIMES.get(name)
    if cls is None:
        available = ", ".join(sorted(_TAX_REGIMES))
        msg = f"Unknown tax regime '{name}'. Available: {available}"
        raise ValueError(msg)
    if cls is NoTaxRegime:
        return NoTaxRegime()
    if cls is ItalianTaxRegime:
        return ItalianTaxRegime(
            default_rate=Decimal(str(params.get("default_rate", "0.26"))),
            government_bond_rate=Decimal(
                str(params.get("government_bond_rate", "0.125"))
            ),
            loss_carryforward_years=int(params.get("loss_carryforward_years", 4)),
        )
    return cls()
