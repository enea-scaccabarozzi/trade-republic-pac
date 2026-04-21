# Backtester Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tax regime support, PAC intraday pricing, variable contributions, and performance improvements (parallel tests, vectorization, MC parallelization) to the backtester.

**Architecture:** Six changes layered bottom-up: (1) new ABCs for tax and contributions, (2) portfolio integration, (3) simulator/config wiring, (4) runner parallelization, (5) data provider optimization, (6) test infrastructure. Each task produces a working, testable increment.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest-xdist, concurrent.futures, numpy, structlog

---

## File Structure

### New Files

| File | Responsibility |
|---|---|
| `src/pac/backtester/engine/tax.py` | `TaxRegime` ABC, `AssetTaxMeta`, `TaxResult`, `ItalianTaxRegime`, `NoTaxRegime`, registry |
| `src/pac/backtester/engine/contributions.py` | `ContributionDistribution` ABC, `ContributionConfig`, `FixedContribution`, `UniformContribution`, `NormalContribution`, resolver |
| `src/pac/backtester/engine/tests/test_tax.py` | Unit tests for tax regimes |
| `src/pac/backtester/engine/tests/test_contributions.py` | Unit tests for contribution distributions |
| `src/pac/backtester/engine/tests/test_portfolio_tax.py` | Integration tests for portfolio + tax |
| `src/pac/backtester/engine/tests/test_parallel_mc.py` | Tests for parallel MC execution |

### Modified Files

| File | Changes |
|---|---|
| `src/pac/backtester/engine/actions.py` | Add `tax: Decimal` to `ExecutedTrade` |
| `src/pac/backtester/engine/portfolio.py` | Inject `TaxRegime` + RNG, apply tax on sells, randomize PAC price |
| `src/pac/backtester/engine/simulator.py` | Wire contributions + tax + RNG, add `total_tax_paid` to `IterationResult` |
| `src/pac/backtester/config.py` | Add `tax_regime`, `tax_params`, `monthly_contribution` union |
| `src/pac/backtester/runner.py` | `ProcessPoolExecutor` for MC, concurrent data fetching |
| `src/pac/backtester/research/context.py` | Pass new config fields through `simulate()`/`simulate_mc()` |
| `src/pac/backtester/data/provider.py` | `itertuples()` fix, `ThreadPoolExecutor` in `fetch_multiple()` |
| `src/pac/backtester/data/proxy_quality.py` | Vectorized daily returns |
| `src/pac/backtester/results/aggregation.py` | Vectorized matrix construction, handle `total_tax_paid` in summary |
| `src/pac/config/models.py` | Add `tax_meta` to `AssetConfig` |
| `src/pac/backtester/engine/__init__.py` | Re-export new types |
| `src/pac/backtester/engine/tests/conftest.py` | Update `make_portfolio()` to accept tax regime + RNG |
| `pyproject.toml` | Add `-n auto --dist loadscope` to pytest addopts |
| `tests/test_setup_gcp.py` | Refactor `setup_method`/`teardown_method` to monkeypatch fixtures |
| `src/pac/backtester/research/tests/test_quantstats.py` | Add `xdist_group` marker |

---

## Task 1: Tax Regime ABC, Models, and NoTaxRegime

**Files:**
- Create: `src/pac/backtester/engine/tax.py`
- Create: `src/pac/backtester/engine/tests/test_tax.py`

- [ ] **Step 1: Write test for TaxResult and AssetTaxMeta models**

```python
# src/pac/backtester/engine/tests/test_tax.py
from __future__ import annotations

from decimal import Decimal

import pytest

from pac.backtester.engine.tax import AssetTaxMeta, NoTaxRegime, TaxResult


class TestTaxResult:
    def test_frozen_model(self) -> None:
        result = TaxResult(
            tax_owed=Decimal("26.00"),
            loss_recorded=Decimal("0"),
            effective_rate=Decimal("0.26"),
        )
        assert result.tax_owed == Decimal("26.00")
        with pytest.raises(Exception):
            result.tax_owed = Decimal("0")  # type: ignore[misc]

    def test_zero_tax(self) -> None:
        result = TaxResult(
            tax_owed=Decimal("0"),
            loss_recorded=Decimal("50.00"),
            effective_rate=Decimal("0"),
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("50.00")


class TestAssetTaxMeta:
    def test_defaults_to_non_government_bond(self) -> None:
        meta = AssetTaxMeta()
        assert meta.government_bond is False

    def test_government_bond_flag(self) -> None:
        meta = AssetTaxMeta(government_bond=True)
        assert meta.government_bond is True


class TestNoTaxRegime:
    def test_name(self) -> None:
        regime = NoTaxRegime()
        assert regime.name == "none"

    def test_always_returns_zero_tax_on_gain(self) -> None:
        regime = NoTaxRegime()
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("0")
        assert result.effective_rate == Decimal("0")

    def test_always_returns_zero_tax_on_loss(self) -> None:
        regime = NoTaxRegime()
        result = regime.compute_tax(
            proceeds=Decimal("900"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("0")

    def test_reset_is_noop(self) -> None:
        regime = NoTaxRegime()
        regime.reset()  # should not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test -k test_tax`
Expected: FAIL — `ModuleNotFoundError: No module named 'pac.backtester.engine.tax'`

- [ ] **Step 3: Implement tax.py with ABC, models, and NoTaxRegime**

```python
# src/pac/backtester/engine/tax.py
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from pydantic import BaseModel


class AssetTaxMeta(BaseModel, frozen=True):
    """Per-asset metadata needed by tax regimes."""

    government_bond: bool = False


class TaxResult(BaseModel, frozen=True):
    """Result of a tax computation on a single sell trade."""

    tax_owed: Decimal
    loss_recorded: Decimal
    effective_rate: Decimal


class TaxRegime(ABC):
    """Abstract base for tax regime implementations.

    Tracks stateful loss carryforward within an MC iteration.
    Call reset() between iterations.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def compute_tax(
        self,
        proceeds: Decimal,
        cost_basis: Decimal,
        asset_meta: AssetTaxMeta,
    ) -> TaxResult: ...

    @abstractmethod
    def reset(self) -> None: ...


class NoTaxRegime(TaxRegime):
    """Opt-out regime — zero tax on all trades."""

    @property
    def name(self) -> str:
        return "none"

    def compute_tax(
        self,
        proceeds: Decimal,
        cost_basis: Decimal,
        asset_meta: AssetTaxMeta,
    ) -> TaxResult:
        return TaxResult(
            tax_owed=Decimal("0"),
            loss_recorded=Decimal("0"),
            effective_rate=Decimal("0"),
        )

    def reset(self) -> None:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `just test -k test_tax`
Expected: PASS

- [ ] **Step 5: Commit**

```
git add src/pac/backtester/engine/tax.py src/pac/backtester/engine/tests/test_tax.py
git commit -m "feat(backtester): add TaxRegime ABC, models, and NoTaxRegime"
```

---

## Task 2: ItalianTaxRegime with Loss Carryforward

**Files:**
- Modify: `src/pac/backtester/engine/tax.py`
- Modify: `src/pac/backtester/engine/tests/test_tax.py`

- [ ] **Step 1: Write tests for ItalianTaxRegime**

Append to `src/pac/backtester/engine/tests/test_tax.py`:

```python
from pac.backtester.engine.tax import ItalianTaxRegime


class TestItalianTaxRegime:
    def test_name(self) -> None:
        regime = ItalianTaxRegime()
        assert regime.name == "italian"

    def test_standard_rate_on_gain(self) -> None:
        regime = ItalianTaxRegime()
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        # 26% of 100 gain = 26
        assert result.tax_owed == Decimal("26.00")
        assert result.loss_recorded == Decimal("0")
        assert result.effective_rate == Decimal("0.26")

    def test_government_bond_reduced_rate(self) -> None:
        regime = ItalianTaxRegime()
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(government_bond=True),
        )
        # 12.5% of 100 gain = 12.50
        assert result.tax_owed == Decimal("12.50")
        assert result.effective_rate == Decimal("0.125")

    def test_loss_records_no_tax(self) -> None:
        regime = ItalianTaxRegime()
        result = regime.compute_tax(
            proceeds=Decimal("900"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("100.00")

    def test_loss_carryforward_offsets_future_gain(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta()
        # Record a loss in fiscal year 2023
        regime.compute_tax(
            proceeds=Decimal("900"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2023,
        )
        # Next gain in same year should be offset
        result = regime.compute_tax(
            proceeds=Decimal("1050"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2023,
        )
        # 50 gain offset by 50 from the 100 loss → 0 tax
        assert result.tax_owed == Decimal("0")

    def test_loss_expires_after_4_years(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta()
        # Loss in 2020
        regime.compute_tax(
            proceeds=Decimal("900"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2020,
        )
        # Gain in 2025 — loss from 2020 has expired (> 4 years)
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2025,
        )
        assert result.tax_owed == Decimal("26.00")

    def test_loss_still_valid_at_4_years(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta()
        # Loss in 2020
        regime.compute_tax(
            proceeds=Decimal("900"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2020,
        )
        # Gain in 2024 — loss from 2020 is still valid (exactly 4 years)
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2024,
        )
        assert result.tax_owed == Decimal("0")

    def test_fifo_loss_consumption(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta()
        # Loss of 50 in 2021
        regime.compute_tax(
            proceeds=Decimal("950"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2021,
        )
        # Loss of 30 in 2022
        regime.compute_tax(
            proceeds=Decimal("970"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2022,
        )
        # Gain of 60 in 2023 — should consume 50 from 2021 + 10 from 2022
        result = regime.compute_tax(
            proceeds=Decimal("1060"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2023,
        )
        # 60 gain - 60 offset = 0 taxable
        assert result.tax_owed == Decimal("0")
        # Still 20 remaining from 2022
        result2 = regime.compute_tax(
            proceeds=Decimal("1010"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2023,
        )
        # 10 gain - 10 offset from remaining 20 = 0
        assert result2.tax_owed == Decimal("0")

    def test_reset_clears_loss_ledger(self) -> None:
        regime = ItalianTaxRegime()
        meta = AssetTaxMeta()
        regime.compute_tax(
            proceeds=Decimal("900"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2023,
        )
        regime.reset()
        # After reset, loss is gone — full tax on gain
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=meta,
            current_year=2023,
        )
        assert result.tax_owed == Decimal("26.00")

    def test_custom_rates(self) -> None:
        regime = ItalianTaxRegime(
            default_rate=Decimal("0.30"),
            government_bond_rate=Decimal("0.15"),
            loss_carryforward_years=2,
        )
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        assert result.tax_owed == Decimal("30.00")

    def test_break_even_trade(self) -> None:
        regime = ItalianTaxRegime()
        result = regime.compute_tax(
            proceeds=Decimal("1000"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        assert result.tax_owed == Decimal("0")
        assert result.loss_recorded == Decimal("0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test -k TestItalianTaxRegime`
Expected: FAIL — `ImportError: cannot import name 'ItalianTaxRegime'`

- [ ] **Step 3: Implement ItalianTaxRegime**

Add to `src/pac/backtester/engine/tax.py`:

```python
_CENTS = Decimal("0.01")


class ItalianTaxRegime(TaxRegime):
    """Italian capital gains tax (imposta sostitutiva).

    Rates: 26% general (redditi diversi), 12.5% for government bonds.
    Loss carryforward: FIFO by fiscal year, expires after configurable years.
    """

    def __init__(
        self,
        *,
        default_rate: Decimal = Decimal("0.26"),
        government_bond_rate: Decimal = Decimal("0.125"),
        loss_carryforward_years: int = 4,
    ) -> None:
        self._default_rate = default_rate
        self._gov_bond_rate = government_bond_rate
        self._carryforward_years = loss_carryforward_years
        # year → remaining loss amount (FIFO consumption order)
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
        gain = proceeds - cost_basis

        if gain <= 0:
            loss = abs(gain)
            if current_year is not None and loss > 0:
                self._loss_ledger[current_year] = (
                    self._loss_ledger.get(current_year, Decimal("0")) + loss
                )
            return TaxResult(
                tax_owed=Decimal("0"),
                loss_recorded=loss.quantize(_CENTS),
                effective_rate=Decimal("0"),
            )

        # Offset gain against carried-forward losses (FIFO by year)
        taxable = gain
        if current_year is not None:
            taxable = self._apply_loss_offset(taxable, current_year)

        rate = self._gov_bond_rate if asset_meta.government_bond else self._default_rate
        tax = (taxable * rate).quantize(_CENTS)

        return TaxResult(
            tax_owed=tax,
            loss_recorded=Decimal("0"),
            effective_rate=rate if taxable > 0 else Decimal("0"),
        )

    def _apply_loss_offset(self, gain: Decimal, current_year: int) -> Decimal:
        remaining = gain
        for year in sorted(self._loss_ledger.keys()):
            if remaining <= 0:
                break
            if current_year - year > self._carryforward_years:
                continue
            available = self._loss_ledger[year]
            offset = min(available, remaining)
            self._loss_ledger[year] -= offset
            remaining -= offset
            if self._loss_ledger[year] <= 0:
                del self._loss_ledger[year]
        return max(remaining, Decimal("0"))

    def reset(self) -> None:
        self._loss_ledger.clear()
```

Note: `compute_tax` gains an optional `current_year` parameter. When called from portfolio, we pass `current_date.year`. This keeps the ABC signature compatible — the base ABC takes `**kwargs` or subclasses add optional params.

Update the ABC to allow subclass-specific extra params:

```python
# In TaxRegime ABC, change compute_tax signature:
@abstractmethod
def compute_tax(
    self,
    proceeds: Decimal,
    cost_basis: Decimal,
    asset_meta: AssetTaxMeta,
    current_year: int | None = None,
) -> TaxResult: ...
```

And update `NoTaxRegime.compute_tax` to accept `current_year: int | None = None` as well.

- [ ] **Step 4: Run test to verify it passes**

Run: `just test -k test_tax`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git add src/pac/backtester/engine/tax.py src/pac/backtester/engine/tests/test_tax.py
git commit -m "feat(backtester): add ItalianTaxRegime with FIFO loss carryforward"
```

---

## Task 3: Tax Regime Registry and Config Integration

**Files:**
- Modify: `src/pac/backtester/engine/tax.py` (add registry)
- Modify: `src/pac/backtester/config.py` (add tax_regime, tax_params fields)
- Modify: `src/pac/config/models.py` (add tax_meta to AssetConfig)
- Modify: `src/pac/backtester/engine/actions.py` (add tax field to ExecutedTrade)
- Modify: `src/pac/backtester/engine/tests/test_tax.py` (add registry tests)

- [ ] **Step 1: Write tests for registry and config**

Append to `src/pac/backtester/engine/tests/test_tax.py`:

```python
from pac.backtester.engine.tax import resolve_tax_regime


class TestTaxRegimeRegistry:
    def test_resolve_italian(self) -> None:
        regime = resolve_tax_regime("italian", {})
        assert regime.name == "italian"
        assert isinstance(regime, ItalianTaxRegime)

    def test_resolve_none(self) -> None:
        regime = resolve_tax_regime("none", {})
        assert regime.name == "none"
        assert isinstance(regime, NoTaxRegime)

    def test_resolve_italian_with_custom_params(self) -> None:
        regime = resolve_tax_regime(
            "italian",
            {"default_rate": 0.30, "loss_carryforward_years": 2},
        )
        assert isinstance(regime, ItalianTaxRegime)
        # Verify custom rate works
        result = regime.compute_tax(
            proceeds=Decimal("1100"),
            cost_basis=Decimal("1000"),
            asset_meta=AssetTaxMeta(),
        )
        assert result.tax_owed == Decimal("30.00")

    def test_resolve_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tax regime"):
            resolve_tax_regime("unknown", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test -k TestTaxRegimeRegistry`
Expected: FAIL — `ImportError: cannot import name 'resolve_tax_regime'`

- [ ] **Step 3: Add registry function to tax.py**

Append to `src/pac/backtester/engine/tax.py`:

```python
_TAX_REGIMES: dict[str, type[TaxRegime]] = {
    "none": NoTaxRegime,
    "italian": ItalianTaxRegime,
}


def resolve_tax_regime(
    name: str,
    params: dict[str, Any],
) -> TaxRegime:
    """Resolve a tax regime by name with optional params."""
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
            loss_carryforward_years=int(
                params.get("loss_carryforward_years", 4)
            ),
        )
    return cls()
```

Add `from typing import Any` to the imports at the top of `tax.py`.

- [ ] **Step 4: Add `tax` field to ExecutedTrade**

In `src/pac/backtester/engine/actions.py`, add `tax: Decimal = Decimal(0)` after the `fee` field (line 70):

```python
class ExecutedTrade(BaseModel, frozen=True):
    date: date
    type: Literal["pac_execution", "hard_rebalance"]
    asset_id: str
    direction: Literal["buy", "sell"]
    amount_eur: Decimal
    quantity: Decimal
    price: Decimal
    fee: Decimal
    tax: Decimal = Decimal(0)
    skipped: bool = False
```

- [ ] **Step 5: Add `tax_meta` to AssetConfig**

In `src/pac/config/models.py`, add import for `AssetTaxMeta` at top and a new field to `AssetConfig`:

```python
# At top — conditional import to avoid circular deps:
from pac.backtester.engine.tax import AssetTaxMeta
```

Wait — this creates a backtester → config circular import. Instead, define `AssetTaxMeta` inline in `config/models.py` (it's a simple frozen model), or keep it in `tax.py` and have the portfolio look it up at runtime from the asset config.

Better approach: add a plain `tax_meta` dict field to `AssetConfig` in `config/models.py`:

```python
# In AssetConfig class, add field:
    tax_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Tax-related metadata (e.g. government_bond: true)",
    )
```

Then in the portfolio/simulator, convert to `AssetTaxMeta`:

```python
meta = AssetTaxMeta(**asset_config.tax_meta)
```

This avoids any circular imports.

- [ ] **Step 6: Add `tax_regime` and `tax_params` to BacktestConfig**

In `src/pac/backtester/config.py`, add two fields:

```python
    tax_regime: str = Field(
        default="italian",
        description="Tax regime to apply ('italian', 'none')",
    )
    tax_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Regime-specific parameters",
    )
```

- [ ] **Step 7: Run all tests to verify nothing is broken**

Run: `just test -k test_tax`
Expected: ALL PASS

Run: `just test`
Expected: ALL PASS (no regressions from new default fields)

- [ ] **Step 8: Commit**

```
git add src/pac/backtester/engine/tax.py src/pac/backtester/engine/tests/test_tax.py src/pac/backtester/engine/actions.py src/pac/backtester/config.py src/pac/config/models.py
git commit -m "feat(backtester): add tax regime registry, config fields, and ExecutedTrade.tax"
```

---

## Task 4: Portfolio Tax Integration and PAC Intraday Price

**Files:**
- Modify: `src/pac/backtester/engine/portfolio.py`
- Create: `src/pac/backtester/engine/tests/test_portfolio_tax.py`

- [ ] **Step 1: Write tests for portfolio tax integration**

```python
# src/pac/backtester/engine/tests/test_portfolio_tax.py
from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

import pytest

from pac.backtester.data.models import PriceBar
from pac.backtester.engine.portfolio import SimulatedPortfolio, SimulatedPosition
from pac.backtester.engine.tax import (
    AssetTaxMeta,
    ItalianTaxRegime,
    NoTaxRegime,
)


def _make_portfolio(
    *,
    tax_regime: ItalianTaxRegime | NoTaxRegime | None = None,
    rng: random.Random | None = None,
    cash: Decimal = Decimal("10000"),
) -> SimulatedPortfolio:
    assets = {
        "stocks": SimulatedPosition(
            asset_id="stocks", isin="IE00BK5BQT80", name="Stocks ETF"
        ),
    }
    return SimulatedPortfolio(
        assets=assets,
        cash=cash,
        pac_volumes={"stocks": Decimal("250")},
        settlement_fee=Decimal("1"),
        spread_bps=Decimal("10"),
        pac_execution_days=[2, 16],
        tax_regime=tax_regime or NoTaxRegime(),
        asset_tax_meta={"stocks": AssetTaxMeta()},
        rng=rng or random.Random(42),
    )


def _bar(price: Decimal) -> PriceBar:
    return PriceBar(
        date=date(2024, 1, 15),
        open=price,
        high=price + Decimal("2"),
        low=price - Decimal("2"),
        close=price,
        volume=1000,
    )


class TestPortfolioTaxOnSell:
    def test_sell_with_italian_regime_deducts_tax(self) -> None:
        regime = ItalianTaxRegime()
        portfolio = _make_portfolio(tax_regime=regime, cash=Decimal("0"))
        # Give the position some shares at known cost
        pos = portfolio._assets["stocks"]
        pos.quantity = Decimal("10")
        pos.avg_cost = Decimal("100")  # bought at 100

        from pac.backtester.engine.actions import HardRebalanceOrder

        prices = {"stocks": _bar(Decimal("200"))}  # sell at ~200
        orders = [
            HardRebalanceOrder(
                asset_id="stocks", direction="sell", amount_eur=Decimal("500")
            )
        ]
        trades = portfolio._execute_rebalance_orders(
            orders, date(2024, 1, 15), prices
        )
        assert len(trades) == 1
        trade = trades[0]
        assert trade.tax > Decimal("0")
        assert trade.direction == "sell"

    def test_sell_with_no_tax_regime_zero_tax(self) -> None:
        portfolio = _make_portfolio(tax_regime=NoTaxRegime(), cash=Decimal("0"))
        pos = portfolio._assets["stocks"]
        pos.quantity = Decimal("10")
        pos.avg_cost = Decimal("100")

        from pac.backtester.engine.actions import HardRebalanceOrder

        prices = {"stocks": _bar(Decimal("200"))}
        orders = [
            HardRebalanceOrder(
                asset_id="stocks", direction="sell", amount_eur=Decimal("500")
            )
        ]
        trades = portfolio._execute_rebalance_orders(
            orders, date(2024, 1, 15), prices
        )
        assert trades[0].tax == Decimal("0")

    def test_buy_never_triggers_tax(self) -> None:
        regime = ItalianTaxRegime()
        portfolio = _make_portfolio(tax_regime=regime)

        from pac.backtester.engine.actions import HardRebalanceOrder

        prices = {"stocks": _bar(Decimal("100"))}
        orders = [
            HardRebalanceOrder(
                asset_id="stocks", direction="buy", amount_eur=Decimal("500")
            )
        ]
        trades = portfolio._execute_rebalance_orders(
            orders, date(2024, 1, 15), prices
        )
        assert trades[0].tax == Decimal("0")


class TestPacIntradayPrice:
    def test_pac_uses_random_price_in_range(self) -> None:
        rng = random.Random(42)
        portfolio = _make_portfolio(rng=rng)
        bar = PriceBar(
            date=date(2024, 1, 2),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=1000,
        )
        prices = {"stocks": bar}
        trades = portfolio.execute_pac(
            date(2024, 1, 2), prices, Decimal("500"), 2
        )
        assert len(trades) == 1
        trade = trades[0]
        # Price should be in [low, high] range, NOT at close
        assert Decimal("90") <= trade.price <= Decimal("110")
        assert trade.price != bar.close  # very unlikely to match exactly

    def test_pac_price_deterministic_with_seed(self) -> None:
        prices = {
            "stocks": PriceBar(
                date=date(2024, 1, 2),
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105"),
                volume=1000,
            )
        }
        p1 = _make_portfolio(rng=random.Random(99))
        t1 = p1.execute_pac(date(2024, 1, 2), prices, Decimal("500"), 2)
        p2 = _make_portfolio(rng=random.Random(99))
        t2 = p2.execute_pac(date(2024, 1, 2), prices, Decimal("500"), 2)
        assert t1[0].price == t2[0].price
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test -k test_portfolio_tax`
Expected: FAIL — `TypeError: SimulatedPortfolio.__init__() got an unexpected keyword argument 'tax_regime'`

- [ ] **Step 3: Modify SimulatedPortfolio to accept tax_regime, asset_tax_meta, and rng**

In `src/pac/backtester/engine/portfolio.py`:

1. Add imports at top:
```python
import random
from pac.backtester.engine.tax import AssetTaxMeta, NoTaxRegime, TaxRegime
```

2. Update `__init__` to accept new params:
```python
    def __init__(
        self,
        assets: dict[str, SimulatedPosition],
        cash: Decimal,
        pac_volumes: dict[str, Decimal],
        settlement_fee: Decimal,
        spread_bps: Decimal,
        pac_execution_days: list[int],
        tax_regime: TaxRegime | None = None,
        asset_tax_meta: dict[str, AssetTaxMeta] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._assets = assets
        self._cash = cash
        self._pac_volumes = dict(pac_volumes)
        self._settlement_fee = settlement_fee
        self._spread_bps = spread_bps
        self._pac_execution_days = pac_execution_days
        self._tax_regime = tax_regime or NoTaxRegime()
        self._asset_tax_meta = asset_tax_meta or {}
        self._rng = rng or random.Random()
        self._pending_actions: list[PendingAction] = []
        self._trade_log: list[ExecutedTrade] = []
        self._pac_months_applied: set[tuple[int, int, int]] = set()
```

3. In `_execute_rebalance_orders`, after computing `sell_qty` and `actual_amount` (the `else` branch for sell direction), add tax computation:

Replace the sell branch (lines 198-208) with:
```python
            else:
                sell_qty = min(quantity, pos.quantity)
                actual_amount = (sell_qty * exec_price).quantize(
                    _CENTS,
                    rounding=ROUND_HALF_UP,
                )
                # Compute tax on realized gain
                sell_cost_basis = (sell_qty * pos.avg_cost).quantize(
                    _CENTS, rounding=ROUND_HALF_UP,
                )
                meta = self._asset_tax_meta.get(
                    order.asset_id, AssetTaxMeta()
                )
                tax_result = self._tax_regime.compute_tax(
                    proceeds=actual_amount,
                    cost_basis=sell_cost_basis,
                    asset_meta=meta,
                    current_year=current_date.year,
                )
                tax_amount = tax_result.tax_owed

                self._cash += actual_amount - self._settlement_fee - tax_amount
                pos.quantity -= sell_qty
                quantity = sell_qty
                recorded_amount = actual_amount
```

4. Update the `ExecutedTrade` construction in the sell path to include `tax=tax_amount`:

```python
            trades.append(
                ExecutedTrade(
                    date=current_date,
                    type="hard_rebalance",
                    asset_id=order.asset_id,
                    direction=order.direction,
                    amount_eur=recorded_amount,
                    quantity=quantity,
                    price=exec_price,
                    fee=self._settlement_fee,
                    tax=tax_amount if order.direction == "sell" else Decimal(0),
                ),
            )
```

Actually, simpler: add a local `tax_amount = Decimal(0)` before the if/else, and only set it in the sell branch. Then always pass `tax=tax_amount` in the trade record.

5. In `execute_pac`, replace `bar.close` with a random price in [low, high]:

Replace lines 260-263:
```python
            # PAC buys at random intraday price (simulates random TR execution hour)
            pac_price = bar.low + (bar.high - bar.low) * Decimal(
                str(self._rng.random())
            )
            quantity = (volume / pac_price).quantize(
                Decimal("0.000001"),
                rounding=ROUND_HALF_UP,
            )
```

Also update the insufficient-cash recalculation path (lines 268-272) to use `pac_price` instead of `bar.close`, and update the `ExecutedTrade` to use `price=pac_price`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test -k test_portfolio_tax`
Expected: ALL PASS

Run: `just test -k "portfolio or simulator"` to check for regressions.
Expected: PASS (existing tests use default `NoTaxRegime` and don't assert on exact PAC price)

- [ ] **Step 5: Commit**

```
git add src/pac/backtester/engine/portfolio.py src/pac/backtester/engine/tests/test_portfolio_tax.py
git commit -m "feat(backtester): integrate tax on sells and PAC intraday random price"
```

---

## Task 5: Contribution Distribution ABC and Implementations

**Files:**
- Create: `src/pac/backtester/engine/contributions.py`
- Create: `src/pac/backtester/engine/tests/test_contributions.py`

- [ ] **Step 1: Write tests for all distribution types**

```python
# src/pac/backtester/engine/tests/test_contributions.py
from __future__ import annotations

import random
from decimal import Decimal

import pytest

from pac.backtester.engine.contributions import (
    ContributionConfig,
    FixedContribution,
    NormalContribution,
    UniformContribution,
    resolve_contribution,
)


class TestFixedContribution:
    def test_always_returns_same_amount(self) -> None:
        dist = FixedContribution(Decimal("500"))
        rng = random.Random(42)
        assert dist.sample(rng) == Decimal("500")
        assert dist.sample(rng) == Decimal("500")

    def test_name(self) -> None:
        assert FixedContribution(Decimal("500")).name == "fixed"


class TestUniformContribution:
    def test_samples_within_range(self) -> None:
        dist = UniformContribution(Decimal("500"), Decimal("750"))
        rng = random.Random(42)
        for _ in range(100):
            val = dist.sample(rng)
            assert Decimal("500") <= val <= Decimal("750")

    def test_deterministic_with_seed(self) -> None:
        dist = UniformContribution(Decimal("500"), Decimal("750"))
        v1 = dist.sample(random.Random(99))
        v2 = dist.sample(random.Random(99))
        assert v1 == v2

    def test_name(self) -> None:
        assert UniformContribution(Decimal("500"), Decimal("750")).name == "uniform"


class TestNormalContribution:
    def test_samples_clipped_to_range(self) -> None:
        dist = NormalContribution(Decimal("500"), Decimal("750"))
        rng = random.Random(42)
        for _ in range(200):
            val = dist.sample(rng)
            assert Decimal("500") <= val <= Decimal("750")

    def test_custom_std(self) -> None:
        dist = NormalContribution(
            Decimal("500"), Decimal("750"), std=Decimal("10")
        )
        rng = random.Random(42)
        values = [dist.sample(rng) for _ in range(100)]
        # With tight std, most values should cluster near mean
        mean = sum(values) / len(values)
        assert Decimal("600") < mean < Decimal("650")

    def test_name(self) -> None:
        assert NormalContribution(Decimal("500"), Decimal("750")).name == "normal"


class TestContributionConfig:
    def test_valid_config(self) -> None:
        cfg = ContributionConfig(min=Decimal("500"), max=Decimal("750"))
        assert cfg.distribution == "uniform"

    def test_min_greater_than_max_rejected(self) -> None:
        with pytest.raises(Exception):
            ContributionConfig(min=Decimal("800"), max=Decimal("500"))


class TestResolveContribution:
    def test_plain_decimal_gives_fixed(self) -> None:
        dist = resolve_contribution(Decimal("500"))
        assert isinstance(dist, FixedContribution)
        assert dist.sample(random.Random()) == Decimal("500")

    def test_config_uniform(self) -> None:
        cfg = ContributionConfig(
            min=Decimal("500"), max=Decimal("750"), distribution="uniform"
        )
        dist = resolve_contribution(cfg)
        assert isinstance(dist, UniformContribution)

    def test_config_normal(self) -> None:
        cfg = ContributionConfig(
            min=Decimal("500"), max=Decimal("750"), distribution="normal"
        )
        dist = resolve_contribution(cfg)
        assert isinstance(dist, NormalContribution)

    def test_unknown_distribution_raises(self) -> None:
        cfg = ContributionConfig(
            min=Decimal("500"), max=Decimal("750"), distribution="beta"
        )
        with pytest.raises(ValueError, match="Unknown distribution"):
            resolve_contribution(cfg)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test -k test_contributions`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement contributions.py**

```python
# src/pac/backtester/engine/contributions.py
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field, model_validator


class ContributionDistribution(ABC):
    """Stateless distribution for monthly contribution sampling."""

    @abstractmethod
    def sample(self, rng: random.Random) -> Decimal: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class FixedContribution(ContributionDistribution):
    def __init__(self, amount: Decimal) -> None:
        self._amount = amount

    def sample(self, rng: random.Random) -> Decimal:
        return self._amount

    @property
    def name(self) -> str:
        return "fixed"


class UniformContribution(ContributionDistribution):
    def __init__(self, min_amount: Decimal, max_amount: Decimal) -> None:
        self._min = min_amount
        self._max = max_amount

    def sample(self, rng: random.Random) -> Decimal:
        raw = self._min + (self._max - self._min) * Decimal(str(rng.random()))
        return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def name(self) -> str:
        return "uniform"


class NormalContribution(ContributionDistribution):
    def __init__(
        self,
        min_amount: Decimal,
        max_amount: Decimal,
        std: Decimal | None = None,
    ) -> None:
        self._min = min_amount
        self._max = max_amount
        self._mean = (min_amount + max_amount) / 2
        self._std = std or (max_amount - min_amount) / 4

    def sample(self, rng: random.Random) -> Decimal:
        raw = Decimal(str(rng.gauss(float(self._mean), float(self._std))))
        clamped = max(self._min, min(self._max, raw))
        return clamped.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def name(self) -> str:
        return "normal"


class ContributionConfig(BaseModel, frozen=True):
    """Config for variable contributions."""

    min: Decimal = Field(ge=0)
    max: Decimal = Field(ge=0)
    distribution: str = "uniform"
    std: Decimal | None = None

    @model_validator(mode="after")
    def _check_range(self) -> ContributionConfig:
        if self.min > self.max:
            msg = f"min ({self.min}) must be <= max ({self.max})"
            raise ValueError(msg)
        return self


_DISTRIBUTIONS: dict[str, type[ContributionDistribution]] = {
    "uniform": UniformContribution,
    "normal": NormalContribution,
}


def resolve_contribution(
    config: Decimal | ContributionConfig,
) -> ContributionDistribution:
    """Resolve contribution config to a distribution instance."""
    if isinstance(config, Decimal):
        return FixedContribution(config)
    dist_name = config.distribution
    if dist_name not in _DISTRIBUTIONS:
        available = ", ".join(sorted(_DISTRIBUTIONS))
        msg = f"Unknown distribution '{dist_name}'. Available: {available}"
        raise ValueError(msg)
    if dist_name == "normal":
        return NormalContribution(config.min, config.max, std=config.std)
    return UniformContribution(config.min, config.max)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `just test -k test_contributions`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git add src/pac/backtester/engine/contributions.py src/pac/backtester/engine/tests/test_contributions.py
git commit -m "feat(backtester): add ContributionDistribution ABC with uniform and normal"
```

---

## Task 6: BacktestConfig Union Type for monthly_contribution

**Files:**
- Modify: `src/pac/backtester/config.py`
- Modify: `src/pac/backtester/engine/tests/test_contributions.py` (add config validation tests)

- [ ] **Step 1: Write config validation tests**

Append to `src/pac/backtester/engine/tests/test_contributions.py`:

```python
from datetime import date

from pac.backtester.config import BacktestConfig


class TestBacktestConfigContribution:
    def test_plain_decimal_accepted(self) -> None:
        cfg = BacktestConfig(
            strategy="noop",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            monthly_contribution=Decimal("500"),
        )
        assert cfg.monthly_contribution == Decimal("500")

    def test_contribution_config_dict_accepted(self) -> None:
        cfg = BacktestConfig(
            strategy="noop",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            monthly_contribution={
                "min": 500,
                "max": 750,
                "distribution": "uniform",
            },
        )
        assert isinstance(cfg.monthly_contribution, ContributionConfig)
        assert cfg.monthly_contribution.min == Decimal("500")

    def test_contribution_config_normal(self) -> None:
        cfg = BacktestConfig(
            strategy="noop",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            monthly_contribution={
                "min": 500,
                "max": 750,
                "distribution": "normal",
                "std": 50,
            },
        )
        assert isinstance(cfg.monthly_contribution, ContributionConfig)
        assert cfg.monthly_contribution.distribution == "normal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test -k TestBacktestConfigContribution`
Expected: FAIL — BacktestConfig doesn't accept dict for monthly_contribution yet

- [ ] **Step 3: Update BacktestConfig to accept union type**

In `src/pac/backtester/config.py`, change the `monthly_contribution` field:

```python
from pac.backtester.engine.contributions import ContributionConfig

class BacktestConfig(BaseModel, frozen=True):
    # ... existing fields ...
    monthly_contribution: Decimal | ContributionConfig = Field(
        default=Decimal("500"), ge=0
    )
```

Remove the `ge=0` constraint from the Field since it only applies to Decimal — Pydantic will validate the union. Add a validator:

```python
    @model_validator(mode="after")
    def _check_contribution(self) -> BacktestConfig:
        mc = self.monthly_contribution
        if isinstance(mc, Decimal) and mc < 0:
            msg = "monthly_contribution must be >= 0"
            raise ValueError(msg)
        return self
```

Actually, the simpler approach is:

```python
    monthly_contribution: Decimal | ContributionConfig = Field(default=Decimal("500"))
```

Pydantic v2 handles discriminated union by type automatically. When the input is a plain number, it becomes `Decimal`. When it's a dict, Pydantic validates it as `ContributionConfig`.

- [ ] **Step 4: Run test to verify it passes**

Run: `just test -k TestBacktestConfigContribution`
Expected: ALL PASS

Run: `just test` to check for regressions (existing code passes `Decimal("500")` — should still work).

- [ ] **Step 5: Commit**

```
git add src/pac/backtester/config.py src/pac/backtester/engine/tests/test_contributions.py
git commit -m "feat(backtester): support variable contributions in BacktestConfig"
```

---

## Task 7: Simulator Wiring — Tax, Contributions, and RNG

**Files:**
- Modify: `src/pac/backtester/engine/simulator.py`
- Modify: `src/pac/backtester/engine/tests/conftest.py` (update `make_portfolio`)
- Add `total_tax_paid` to `IterationResult`

- [ ] **Step 1: Add `total_tax_paid` to IterationResult**

In `src/pac/backtester/engine/simulator.py`, update the `IterationResult` class:

```python
class IterationResult(BaseModel, frozen=True):
    iteration: int
    daily_values: list[DayResult]
    trades: list[ExecutedTrade]
    final_value: Decimal
    total_tax_paid: Decimal = Decimal(0)
    indicator_snapshots: dict[str, list[IndicatorDataPoint]] = {}
    signal_log: list[SignalRecord] = []
    strategy_events: list[StrategyEvent] = []
```

- [ ] **Step 2: Update BacktestSimulator to wire tax, contributions, and RNG**

In `src/pac/backtester/engine/simulator.py`:

Add imports:
```python
from pac.backtester.engine.contributions import (
    ContributionConfig,
    ContributionDistribution,
    resolve_contribution,
)
from pac.backtester.engine.tax import (
    AssetTaxMeta,
    TaxRegime,
    resolve_tax_regime,
)
```

In `__init__`, after the existing code, add:

```python
        # Resolve tax regime
        self._tax_regime = resolve_tax_regime(
            config.tax_regime, config.tax_params
        )

        # Build asset tax metadata from settings
        self._asset_tax_meta: dict[str, AssetTaxMeta] = {
            a.id: AssetTaxMeta(**a.tax_meta) for a in settings.assets
        }

        # Resolve contribution distribution
        self._contribution_dist: ContributionDistribution = resolve_contribution(
            config.monthly_contribution
        )
```

In `_build_portfolio`, pass the new params:

```python
    def _build_portfolio(self) -> SimulatedPortfolio:
        assets = {
            a.id: SimulatedPosition(
                asset_id=a.id,
                isin=a.isin,
                name=a.name,
            )
            for a in self._settings.assets
        }
        return SimulatedPortfolio(
            assets=assets,
            cash=self._config.initial_cash,
            pac_volumes=dict(self._initial_pac_volumes),
            settlement_fee=self._config.settlement_fee,
            spread_bps=self._config.spread_bps,
            pac_execution_days=self._config.pac_execution_days,
            tax_regime=self._tax_regime,
            asset_tax_meta=self._asset_tax_meta,
            rng=self._rng,
        )
```

In `__init__`, fix `_initial_pac_volumes` — when `monthly_contribution` is a `ContributionConfig`, use the midpoint for initial volumes:

```python
        mc = config.monthly_contribution
        base_contribution = (
            mc if isinstance(mc, Decimal) else (mc.min + mc.max) / 2
        )
        self._initial_pac_volumes: dict[str, Decimal] = {
            aid: (base_contribution * pct / Decimal(100))
            for aid, pct in targets.items()
        }
```

In `run_iteration`, before the trading day loop, sample the first month's contribution. Track which month we're in and re-sample at each new month's first PAC day:

Replace the PAC execution section (around line 240) — instead of passing `self._config.monthly_contribution`, pass the sampled amount:

```python
            if pac_day is not None:
                # Sample new monthly contribution on first PAC day of each month
                month_key = (d.year, d.month)
                if month_key not in sampled_months:
                    sampled_months[month_key] = self._contribution_dist.sample(
                        self._rng
                    )
                monthly_amount = sampled_months[month_key]

                pre_pac_snapshot = portfolio.snapshot(d, prices)
                pre_pac_report = calculate_deviations(
                    pre_pac_snapshot, self._settings,
                )
                pac_adj = self._strategy.on_pac_date(
                    pre_pac_snapshot, pre_pac_report, d, portfolio.pac_volumes,
                )
                if pac_adj is not None:
                    portfolio.apply_pac_adjustment(pac_adj)
                portfolio.execute_pac(d, prices, monthly_amount, pac_day)
```

Add `sampled_months: dict[tuple[int, int], Decimal] = {}` near the top of `run_iteration`.

In `run_iteration`, also reset the tax regime at the start:

```python
    def run_iteration(self, iteration: int) -> IterationResult:
        self._strategy.reset()
        self._tax_regime.reset()
        portfolio = self._build_portfolio()
        # ...
```

At the return, compute `total_tax_paid`:

```python
        total_tax = sum(
            (t.tax for t in portfolio.trade_log), Decimal(0)
        )

        return IterationResult(
            iteration=iteration,
            daily_values=daily_values,
            trades=portfolio.trade_log,
            final_value=(...),
            total_tax_paid=total_tax,
            # ...
        )
```

- [ ] **Step 3: Update engine/tests/conftest.py — make_portfolio()**

Update `make_portfolio` in `src/pac/backtester/engine/tests/conftest.py` to accept optional `tax_regime` and `rng` parameters, defaulting to `NoTaxRegime()` and `random.Random(42)`.

Add imports:
```python
import random
from pac.backtester.engine.tax import NoTaxRegime, TaxRegime
```

Update the function signature and body to pass these through to `SimulatedPortfolio`.

- [ ] **Step 4: Run full test suite**

Run: `just test`
Expected: ALL PASS — existing tests use defaults (`NoTaxRegime`, `FixedContribution`)

- [ ] **Step 5: Commit**

```
git add src/pac/backtester/engine/simulator.py src/pac/backtester/engine/tests/conftest.py
git commit -m "feat(backtester): wire tax regime, variable contributions, and RNG through simulator"
```

---

## Task 8: Update Results Aggregation for Tax

**Files:**
- Modify: `src/pac/backtester/results/aggregation.py`

- [ ] **Step 1: Update `_compute_summary` to handle variable contributions**

In `src/pac/backtester/results/aggregation.py`, the `_compute_summary` function currently computes `total_invested` using `config.monthly_contribution` directly (line 253). This breaks when `monthly_contribution` is a `ContributionConfig`.

Replace lines 253-262 with:

```python
    mc = config.monthly_contribution
    if isinstance(mc, Decimal):
        contribution_per_pac = mc / Decimal(len(config.pac_execution_days))
        total_invested = (
            float(config.initial_cash)
            + float(contribution_per_pac) * pac_count
        )
    else:
        # Variable contributions — estimate from median iteration's actual trades
        pac_total = sum(
            float(t.amount_eur) for t in median_iter.trades if t.type == "pac_execution"
        )
        total_invested = float(config.initial_cash) + pac_total
```

Add import at top:
```python
from pac.backtester.engine.contributions import ContributionConfig
```

- [ ] **Step 2: Add total_tax_paid to SummaryStats**

Check if `SummaryStats` in `src/pac/backtester/results/models.py` needs a `total_tax` field. If desired, add a `ConfidenceInterval` for total tax across iterations:

```python
    total_tax: ConfidenceInterval | None = None
```

And compute it in `_compute_summary`:

```python
    tax_per_iter = [
        sum(float(t.tax) for t in it.trades) for it in iterations
    ]
    total_tax = ConfidenceInterval(
        p5=float(np.percentile(tax_per_iter, 5)),
        median=float(np.percentile(tax_per_iter, 50)),
        p95=float(np.percentile(tax_per_iter, 95)),
    ) if any(t > 0 for t in tax_per_iter) else None
```

- [ ] **Step 3: Run tests**

Run: `just test -k aggregation`
Expected: PASS

Run: `just test`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```
git add src/pac/backtester/results/aggregation.py src/pac/backtester/results/models.py
git commit -m "feat(backtester): handle variable contributions and tax in results aggregation"
```

---

## Task 9: Update ResearchContext to Pass New Config Fields

**Files:**
- Modify: `src/pac/backtester/research/context.py`

- [ ] **Step 1: Update `simulate()` and `simulate_mc()` to accept tax and contribution params**

In `context.py`, update the `simulate()` method signature to accept optional `tax_regime` and `monthly_contribution`:

```python
    def simulate(
        self,
        strategy: str,
        params: dict[str, Any] | None = None,
        *,
        tax_regime: str = "italian",
        tax_params: dict[str, Any] | None = None,
        monthly_contribution: Decimal | dict[str, Any] | None = None,
    ) -> IterationResult:
```

Pass these through to `BacktestConfig` construction.

Similarly update `simulate_mc()`.

For `monthly_contribution`, if it's a dict, construct `ContributionConfig(**monthly_contribution)` before passing to `BacktestConfig`. If None, use the existing default.

- [ ] **Step 2: Run research tests**

Run: `just test -k research`
Expected: ALL PASS (defaults match current behavior)

- [ ] **Step 3: Commit**

```
git add src/pac/backtester/research/context.py
git commit -m "feat(backtester): expose tax regime and variable contributions in ResearchContext"
```

---

## Task 10: Update Engine __init__.py Exports

**Files:**
- Modify: `src/pac/backtester/engine/__init__.py`

- [ ] **Step 1: Add new exports**

```python
from pac.backtester.engine.contributions import (
    ContributionConfig,
    ContributionDistribution,
    FixedContribution,
    NormalContribution,
    UniformContribution,
)
from pac.backtester.engine.tax import (
    AssetTaxMeta,
    ItalianTaxRegime,
    NoTaxRegime,
    TaxRegime,
    TaxResult,
)
```

Add these to `__all__`.

- [ ] **Step 2: Run typecheck**

Run: `just typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```
git add src/pac/backtester/engine/__init__.py
git commit -m "refactor(backtester): export tax and contribution types from engine package"
```

---

## Task 11: DataFrame Vectorization

**Files:**
- Modify: `src/pac/backtester/data/provider.py`
- Modify: `src/pac/backtester/data/proxy_quality.py`
- Modify: `src/pac/backtester/results/aggregation.py`

- [ ] **Step 1: Fix `iterrows()` in provider.py**

In `src/pac/backtester/data/provider.py`, replace lines 138-148:

```python
        bars = [
            PriceBar(
                date=idx.date(),
                open=Decimal(str(row["Open"])),
                high=Decimal(str(row["High"])),
                low=Decimal(str(row["Low"])),
                close=Decimal(str(row["Close"])),
                volume=int(row["Volume"]),
            )
            for idx, row in df.iterrows()
        ]
```

With:

```python
        bars = [
            PriceBar(
                date=row.Index.date(),
                open=Decimal(str(row.Open)),
                high=Decimal(str(row.High)),
                low=Decimal(str(row.Low)),
                close=Decimal(str(row.Close)),
                volume=int(row.Volume),
            )
            for row in df.itertuples()
        ]
```

- [ ] **Step 2: Vectorize daily returns in proxy_quality.py**

In `src/pac/backtester/data/proxy_quality.py`, replace lines 69-80:

```python
    # compute daily returns over overlap
    proxy_returns: list[float] = []
    target_returns: list[float] = []
    for i in range(1, len(overlap_dates)):
        d_prev, d_curr = overlap_dates[i - 1], overlap_dates[i]
        p_prev = float(proxy_dates[d_prev].close)
        p_curr = float(proxy_dates[d_curr].close)
        t_prev = float(target_dates[d_prev].close)
        t_curr = float(target_dates[d_curr].close)
        if p_prev > 0 and t_prev > 0:
            proxy_returns.append(p_curr / p_prev - 1)
            target_returns.append(t_curr / t_prev - 1)
```

With:

```python
    # compute daily returns over overlap (vectorized)
    import numpy as np

    proxy_prices = np.array(
        [float(proxy_dates[d].close) for d in overlap_dates]
    )
    target_prices = np.array(
        [float(target_dates[d].close) for d in overlap_dates]
    )

    # Mask out zero prices to avoid division by zero
    valid = (proxy_prices[:-1] > 0) & (target_prices[:-1] > 0)
    proxy_ret = np.diff(proxy_prices) / np.where(
        proxy_prices[:-1] > 0, proxy_prices[:-1], 1.0
    )
    target_ret = np.diff(target_prices) / np.where(
        target_prices[:-1] > 0, target_prices[:-1], 1.0
    )
    proxy_returns = proxy_ret[valid].tolist()
    target_returns = target_ret[valid].tolist()
```

- [ ] **Step 3: Vectorize matrix construction in aggregation.py**

In `src/pac/backtester/results/aggregation.py`, replace the nested loops in `_build_equity_curve` (lines 152-155):

```python
    matrix = np.empty((n_iters, n_dates))
    for i, it in enumerate(iterations):
        for j, dv in enumerate(it.daily_values):
            matrix[i, j] = float(dv.total_value)
```

With:

```python
    matrix = np.array(
        [[float(dv.total_value) for dv in it.daily_values] for it in iterations]
    )
```

Similarly in `_build_allocations`, replace the triple-nested loop (lines 186-189):

```python
        m = np.empty((n_iters, n_dates))
        for i, it in enumerate(iterations):
            for j, dv in enumerate(it.daily_values):
                m[i, j] = float(dv.allocations.get(aid, Decimal(0)))
```

With:

```python
        m = np.array([
            [float(dv.allocations.get(aid, Decimal(0))) for dv in it.daily_values]
            for it in iterations
        ])
```

And for the cash matrix (lines 193-197):

```python
    cash_matrix = np.array([
        [
            (float(dv.cash) / float(dv.total_value) * 100)
            if float(dv.total_value) > 0
            else 0.0
            for dv in it.daily_values
        ]
        for it in iterations
    ])
```

- [ ] **Step 4: Run tests to verify no regressions**

Run: `just test`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git add src/pac/backtester/data/provider.py src/pac/backtester/data/proxy_quality.py src/pac/backtester/results/aggregation.py
git commit -m "perf(backtester): vectorize DataFrame iteration and matrix construction"
```

---

## Task 12: Concurrent Data Fetching

**Files:**
- Modify: `src/pac/backtester/data/provider.py`
- Modify: `src/pac/backtester/runner.py`

- [ ] **Step 1: Add ThreadPoolExecutor to fetch_multiple()**

In `src/pac/backtester/data/provider.py`, replace `fetch_multiple` (lines 165-177):

```python
    def fetch_multiple(
        self,
        requests: list[DataRequest],
    ) -> dict[str, PriceSeries]:
        """Fetch data for multiple tickers concurrently.

        Uses a thread pool for parallel I/O. Falls back to sequential
        for single requests.
        """
        if len(requests) <= 1:
            return {req.ticker: self.fetch(req) for req in requests}

        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: dict[str, PriceSeries] = {}
        max_workers = min(len(requests), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self.fetch, req): req.ticker for req in requests
            }
            for future in as_completed(futures):
                ticker = futures[future]
                results[ticker] = future.result()
        return results
```

- [ ] **Step 2: Update runner.py to use concurrent data fetching**

In `src/pac/backtester/runner.py`, replace the sequential asset fetch loop (lines 113-124):

```python
        provider = MarketDataProvider()
        price_data: dict[str, PriceSeries] = {}
        for a in settings.assets:
            if a.ticker is None:
                continue
            series = provider.fetch_with_proxy(
                ticker=a.ticker,
                start=config.start_date,
                end=config.end_date,
                proxy_chain=a.proxy_chain or None,
                primary_currency=a.currency,
            )
            price_data[a.ticker] = series
```

With a concurrent approach using ThreadPoolExecutor:

```python
        from concurrent.futures import ThreadPoolExecutor, as_completed

        provider = MarketDataProvider()
        assets_with_tickers = [a for a in settings.assets if a.ticker]

        def _fetch_asset(a: AssetConfig) -> tuple[str, PriceSeries]:
            series = provider.fetch_with_proxy(
                ticker=a.ticker,  # type: ignore[arg-type]
                start=config.start_date,
                end=config.end_date,
                proxy_chain=a.proxy_chain or None,
                primary_currency=a.currency,
            )
            return a.ticker, series  # type: ignore[return-value]

        price_data: dict[str, PriceSeries] = {}
        if len(assets_with_tickers) <= 1:
            for a in assets_with_tickers:
                ticker, series = _fetch_asset(a)
                price_data[ticker] = series
        else:
            max_workers = min(len(assets_with_tickers), 8)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(_fetch_asset, a): a for a in assets_with_tickers
                }
                for future in as_completed(futures):
                    ticker, series = future.result()
                    price_data[ticker] = series
```

Add import `from pac.config.models import AssetConfig` if not already present.

- [ ] **Step 3: Run tests**

Run: `just test`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```
git add src/pac/backtester/data/provider.py src/pac/backtester/runner.py
git commit -m "perf(backtester): concurrent data fetching with ThreadPoolExecutor"
```

---

## Task 13: Parallel Monte Carlo Execution

**Files:**
- Modify: `src/pac/backtester/runner.py`
- Modify: `src/pac/backtester/engine/simulator.py`
- Create: `src/pac/backtester/engine/tests/test_parallel_mc.py`

- [ ] **Step 1: Write test for parallel MC producing same results as sequential**

```python
# src/pac/backtester/engine/tests/test_parallel_mc.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from pac.backtester.config import BacktestConfig
from pac.backtester.engine.simulator import (
    BacktestSimulator,
    run_iterations_parallel,
)
from pac.backtester.engine.tests.conftest import (
    make_settings,
    make_three_asset_price_data,
)
from pac.backtester.strategies.base import BacktestStrategy
from pac.models.signals import Signal
from pac.models.portfolio import PortfolioSnapshot
from pac.analysis.deviation import DeviationReport
from pac.backtester.engine.actions import Action
from pac.rules.registry import SignalRegistry


class _NoopParams(BaseModel):
    pass


class _NoopStrategy(BacktestStrategy[_NoopParams]):
    name = "noop_parallel_test"

    def on_signals(
        self,
        signals: list[Signal],
        snapshot: PortfolioSnapshot,
        report: DeviationReport,
        current_date: date,
    ) -> list[Action]:
        return []


def test_parallel_mc_matches_sequential() -> None:
    """Parallel MC must produce identical results to sequential with same seeds."""
    settings = make_settings()
    price_data = make_three_asset_price_data(date(2024, 1, 1), 60)
    config = BacktestConfig(
        strategy="noop_parallel_test",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 29),
        monte_carlo_iterations=4,
    )
    registry = SignalRegistry()
    strategy = _NoopStrategy(_NoopParams())

    # Sequential: each iteration gets rng_seed = base_seed + iteration
    seq_results = []
    for i in range(4):
        sim = BacktestSimulator(
            config, settings, price_data, registry, strategy,
            rng_seed=42 + i,
        )
        seq_results.append(sim.run_iteration(i))

    # Parallel
    par_results = run_iterations_parallel(
        config, settings, price_data, registry, strategy,
        seed=42, max_workers=2,
    )

    # Final values must match (order by iteration index)
    seq_sorted = sorted(seq_results, key=lambda r: r.iteration)
    par_sorted = sorted(par_results, key=lambda r: r.iteration)
    for s, p in zip(seq_sorted, par_sorted, strict=True):
        assert s.final_value == p.final_value
        assert s.iteration == p.iteration
```

Note: This test references a `run_iterations_parallel` function and `_NoopParams` — adjust imports based on actual module structure. The key assertion is that parallel results match sequential when using deterministic seeds.

- [ ] **Step 2: Run test to verify it fails**

Run: `just test -k test_parallel_mc`
Expected: FAIL — `ImportError: cannot import name 'run_iterations_parallel'`

- [ ] **Step 3: Implement parallel MC execution**

In `src/pac/backtester/engine/simulator.py`, add a module-level worker function (must be picklable):

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
import os


def _iteration_worker(
    config: BacktestConfig,
    settings: Settings,
    price_data: dict[str, PriceSeries],
    signal_configs: list[SignalConfig],
    strategy_name: str,
    strategy_params: dict[str, Any],
    iteration: int,
    seed: int,
) -> IterationResult:
    """Top-level picklable function for parallel MC execution."""
    from pac.backtester.strategies.discovery import discover_strategies
    from pac.rules.discovery import discover_rules

    rule_classes = discover_rules()
    registry = SignalRegistry()
    for rule_cls in rule_classes.values():
        registry.register(rule_cls)

    strategies = discover_strategies()
    strategy_cls = strategies[strategy_name]
    params = strategy_cls.params_model.model_validate(strategy_params)
    strategy = strategy_cls(params)

    simulator = BacktestSimulator(
        config, settings, price_data, registry, strategy,
        rng_seed=seed + iteration,
    )
    return simulator.run_iteration(iteration)


def run_iterations_parallel(
    config: BacktestConfig,
    settings: Settings,
    price_data: dict[str, PriceSeries],
    registry: SignalRegistry,
    strategy: BacktestStrategy[Any],
    *,
    seed: int | None = None,
    max_workers: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[IterationResult]:
    """Run MC iterations in parallel using ProcessPoolExecutor."""
    n = config.monte_carlo_iterations
    base_seed = seed or 0

    if n <= 1:
        sim = BacktestSimulator(
            config, settings, price_data, registry, strategy,
            rng_seed=base_seed,
        )
        result = sim.run_iteration(0)
        if on_progress:
            on_progress(1, 1)
        return [result]

    workers = min(
        max_workers or os.cpu_count() or 4,
        n,
    )

    results: list[IterationResult] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _iteration_worker,
                config,
                settings,
                price_data,
                settings.signals,
                config.strategy,
                config.strategy_params,
                i,
                base_seed,
            ): i
            for i in range(n)
        }
        for future in as_completed(futures):
            results.append(future.result())
            if on_progress:
                on_progress(len(results), n)

    return results
```

Add necessary imports: `from collections.abc import Callable`, `import os`.

- [ ] **Step 4: Update runner.py to use parallel execution**

In `src/pac/backtester/runner.py`, replace the sequential MC loop (lines 176-181):

```python
    total = config.monte_carlo_iterations
    iterations: list[IterationResult] = []
    for i in range(total):
        iterations.append(simulator.run_iteration(i))
        if on_progress is not None:
            on_progress(i + 1, total)
```

With:

```python
    from pac.backtester.engine.simulator import run_iterations_parallel

    iterations = run_iterations_parallel(
        config,
        settings,
        price_data,
        registry,
        strategy,
        seed=seed,
        on_progress=on_progress,
    )
```

Remove the `simulator = BacktestSimulator(...)` instantiation above it (lines 168-175), since `run_iterations_parallel` handles simulator creation internally.

- [ ] **Step 5: Run tests**

Run: `just test -k test_parallel_mc`
Expected: PASS

Run: `just test`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```
git add src/pac/backtester/engine/simulator.py src/pac/backtester/runner.py src/pac/backtester/engine/tests/test_parallel_mc.py
git commit -m "perf(backtester): parallel Monte Carlo execution with ProcessPoolExecutor"
```

---

## Task 14: Parallel pytest Execution

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_setup_gcp.py`
- Modify: `src/pac/backtester/research/tests/test_quantstats.py`

- [ ] **Step 1: Refactor test_setup_gcp.py to use monkeypatch**

Replace `TestRunGcloud.setup_method`/`teardown_method` (lines 32-41) with a fixture approach. Remove the class-level setup/teardown and add a fixture:

At the top of the file, add a fixture that all tests in `TestRunGcloud` and `TestSelectAccount` use:

```python
@pytest.fixture(autouse=True)
def _reset_active_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset _ACTIVE_ACCOUNT to None before each test."""
    import scripts.setup_gcp as gcp
    monkeypatch.setattr(gcp, "_ACTIVE_ACCOUNT", None)
```

Remove `setup_method` and `teardown_method` from both `TestRunGcloud` and `TestSelectAccount` classes.

Also remove the manual save/restore in `test_prepends_gcloud_to_args` (lines 72-80) and `test_injects_account_flag_when_active_account_set` (lines 82-95) — the autouse fixture already handles reset. For the test that sets `_ACTIVE_ACCOUNT = "user@example.com"`, use `monkeypatch.setattr` directly in the test:

```python
    def test_injects_account_flag_when_active_account_set(
        self, mock_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.setup_gcp as gcp
        monkeypatch.setattr(gcp, "_ACTIVE_ACCOUNT", "user@example.com")
        gcp._run_gcloud(["projects", "list"])
        cmd = mock_run.call_args[0][0]
        assert cmd[:4] == ["gcloud", "--account", "user@example.com", "projects"]
```

- [ ] **Step 2: Add xdist_group marker to quantstats tests**

In `src/pac/backtester/research/tests/test_quantstats.py`, add the marker to both matplotlib classes:

```python
@pytest.mark.xdist_group("matplotlib")
class TestQuantstatsPlot:
    # ...

@pytest.mark.xdist_group("matplotlib")
class TestQuantstatsSavePlots:
    # ...
```

- [ ] **Step 3: Enable pytest-xdist in pyproject.toml**

In `pyproject.toml`, update the addopts line:

```toml
addopts = "--ignore-glob=**/dashboard.legacy/** -n auto --dist loadscope"
```

- [ ] **Step 4: Run full test suite in parallel**

Run: `just test`
Expected: ALL PASS with parallel execution (should see "N workers" in output)

- [ ] **Step 5: Commit**

```
git add pyproject.toml tests/test_setup_gcp.py src/pac/backtester/research/tests/test_quantstats.py
git commit -m "perf(tests): enable parallel pytest execution with xdist"
```

---

## Task 15: Final Integration Test and Validation

**Files:**
- No new files — validation only

- [ ] **Step 1: Run full test suite**

Run: `just validate`
Expected: lint + typecheck + tests all PASS

- [ ] **Step 2: Run typecheck**

Run: `just typecheck`
Expected: PASS — no new mypy errors

- [ ] **Step 3: Run linter**

Run: `just lint`
Expected: PASS

- [ ] **Step 4: Run a quick smoke test of the full pipeline**

If `pac.yaml` is configured with tickers, run:
```
just backtest-validate-quick
```

Otherwise, verify that `BacktestConfig` with new fields validates correctly:

```python
python -c "
from decimal import Decimal
from datetime import date
from pac.backtester.config import BacktestConfig
cfg = BacktestConfig(
    strategy='pac_alignment',
    start_date=date(2024,1,1),
    end_date=date(2024,12,31),
    tax_regime='italian',
    monthly_contribution={'min': 500, 'max': 750, 'distribution': 'uniform'},
)
print('Config OK:', cfg.tax_regime, type(cfg.monthly_contribution))
"
```

Expected: `Config OK: italian <class 'pac.backtester.engine.contributions.ContributionConfig'>`

- [ ] **Step 5: Commit any final fixes**

If any fixes were needed, commit them individually with descriptive messages.
