"""Cost models for portfolio rebalancing.

The user asked explicitly for costs as a plugin component. This module
provides a Protocol + several implementations, from the simple flat-bps
of Chagas' notebooks up to a realistic Brazilian B3 cost stack.

All cost models follow the same interface:

    cost = model.cost(current_weights, new_weights, prices=None, dt=None)

returning a scalar fraction of NAV (e.g. 0.0015 = 15 bps of NAV).

Costs enter the backtest as a deduction to the portfolio log-return at the
rebalancing date, following Chagas' pattern:

    port_logrets[t] -= log1p(rebal_costs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class CostModel(Protocol):
    """Anything that can quote the cost of moving from one allocation to another."""

    def cost(
        self,
        current_weights: pd.Series | np.ndarray,
        new_weights: pd.Series | np.ndarray,
        prices: Optional[pd.Series] = None,
        nav: Optional[float] = None,
        dt: Optional[pd.Timestamp] = None,
    ) -> float: ...


# ---------------------------------------------------------------------------
# Flat cost (Chagas' baseline)
# ---------------------------------------------------------------------------

@dataclass
class FlatCost:
    """Linear cost: rate × |Δw| (Chagas' standard: 15bps to 2bps).

    Used in all 4 Chagas notebooks with values:
    - 15 bps (0.0015) for monthly equity rebalancing (nb1)
    - 2 bps (0.0002) for monthly commodity futures (nb3, nb4)
    - 10 bps (0.0010) for weekly BR equities (Ex1.xlsx)
    """

    rate: float = 0.0015
    name: str = "flat"

    def cost(self, current_weights, new_weights, prices=None, nav=None, dt=None):
        cur = np.asarray(current_weights).flatten()
        new = np.asarray(new_weights).flatten()
        # Align lengths defensively
        if cur.shape != new.shape:
            raise ValueError(f"Weight shapes differ: {cur.shape} vs {new.shape}")
        return float(self.rate * np.sum(np.abs(new - cur)))


# ---------------------------------------------------------------------------
# Tiered cost (large trades cheaper)
# ---------------------------------------------------------------------------

@dataclass
class TieredCost:
    """Piecewise-linear cost: tiers defined by trade size as fraction of NAV.

    Example:
        TieredCost(tiers=[(0.01, 0.0030), (0.05, 0.0020), (1.0, 0.0010)])
    means: 30 bps up to 1% trade, 20 bps from 1-5%, 10 bps above 5%.
    """

    tiers: list[tuple[float, float]] = field(default_factory=lambda: [(1.0, 0.0015)])
    name: str = "tiered"

    def cost(self, current_weights, new_weights, prices=None, nav=None, dt=None):
        cur = np.asarray(current_weights).flatten()
        new = np.asarray(new_weights).flatten()
        deltas = np.abs(new - cur)
        total = 0.0
        # Sort tiers by upper bound ascending
        tiers = sorted(self.tiers, key=lambda t: t[0])
        for delta in deltas:
            prev_ub = 0.0
            remaining = delta
            for ub, rate in tiers:
                slice_size = min(remaining, ub - prev_ub)
                if slice_size <= 0:
                    break
                total += slice_size * rate
                remaining -= slice_size
                prev_ub = ub
                if remaining <= 0:
                    break
        return float(total)


# ---------------------------------------------------------------------------
# B3 realistic cost
# ---------------------------------------------------------------------------

@dataclass
class B3RealisticCost:
    """B3 (Brazil) realistic cost model.

    Components (approximate 2025 values, can be configured):
    - corretagem: usually 0 for retail at modern brokers (XP, BTG, Modal, Avenue Securities)
                  but kept for institutional flows
    - emolumentos B3: ~0.003% for equity day trades, ~0.005% for swing
    - liquidação B3: ~0.0275% (Câmara de Ações)
    - ISS over corretagem: 2-5% (municipal, applies to brokerage)
    - taxa Selic over funding: ignored here (financing assumed neutral)

    For futures, costs are typically much lower (B3 emolumentos diferentes).
    Use `futures=True` to apply the futures-style costs.
    """

    corretagem_rate: float = 0.0       # 0 bps default (modern retail)
    emolumentos: float = 0.00003       # 0.3 bps
    liquidacao: float = 0.000275       # 2.75 bps
    iss_rate: float = 0.02             # 2% over corretagem
    futures: bool = False
    name: str = "b3_realistic"

    def cost(self, current_weights, new_weights, prices=None, nav=None, dt=None):
        cur = np.asarray(current_weights).flatten()
        new = np.asarray(new_weights).flatten()
        gross_turnover = float(np.sum(np.abs(new - cur)))

        if self.futures:
            # Approx B3 futures: ~0.5 bps round-trip per side
            return gross_turnover * 0.00005

        brokerage = self.corretagem_rate * (1 + self.iss_rate)
        per_side = self.emolumentos + self.liquidacao + brokerage
        return gross_turnover * per_side


# ---------------------------------------------------------------------------
# Offshore cost (FX + brokerage)
# ---------------------------------------------------------------------------

@dataclass
class OffshoreCost:
    """Offshore equity/ETF cost model (US + Europe).

    Approximations:
    - Brokerage: ~0-5 bps at modern platforms (IB, Avenue, Inter Invest)
    - SEC fee (US sells): ~0.00229% (capped)
    - FX spread: 30-100 bps each conversion (PTAX vs comercial)
    """

    brokerage_rate: float = 0.0005    # 5 bps default
    sec_fee: float = 0.0000229         # 0.229 bps sell-side US
    fx_spread: float = 0.005           # 50 bps each FX conversion
    needs_fx: bool = True              # whether trades cross BRL/USD
    name: str = "offshore"

    def cost(self, current_weights, new_weights, prices=None, nav=None, dt=None):
        cur = np.asarray(current_weights).flatten()
        new = np.asarray(new_weights).flatten()
        gross = float(np.sum(np.abs(new - cur)))
        base = gross * (self.brokerage_rate + self.sec_fee / 2)
        fx = gross * self.fx_spread if self.needs_fx else 0.0
        return base + fx


# ---------------------------------------------------------------------------
# Tax-aware cost (BR IR on realized gains)
# ---------------------------------------------------------------------------

@dataclass
class TaxAwareCost:
    """Brazilian IR (income tax) on realized capital gains.

    BR tax bracket for portfolio investments (2025):
    - Equities (swing trade): 15% on net monthly gains > R$ 20k threshold
    - Equities (day trade): 20% always
    - Real-estate funds (FIIs): 20% on each sale (no monthly threshold)
    - Fixed income / Renda fixa: 22.5% to 15% (regressive by holding period)
    - Funds (FII multimercado/RV via XML): 15% or 20%
    - ETFs of foreign equity: 15% regardless of period (since 2024 reform)

    This model treats taxes as a cost realized at rebalancing (cash drag).

    Caveats:
    - Real tax accounting is lot-by-lot (FIFO) and depends on cumulative
      monthly position. This is a simplified rolling approximation.
    - Losses (prejuízos) can be carried forward to offset future gains;
      not modeled here.
    """

    equity_rate: float = 0.15
    fii_rate: float = 0.20
    bond_rate: float = 0.175        # mid-range default; vary by holding period
    foreign_rate: float = 0.15
    monthly_threshold_brl: float = 20_000.0
    asset_classes: dict[str, str] = field(default_factory=dict)
    name: str = "tax_aware_br"

    def cost(self, current_weights, new_weights, prices=None, nav=None, dt=None):
        if nav is None or prices is None:
            # Without NAV and prices, fall back to a conservative flat estimate
            cur = np.asarray(current_weights).flatten()
            new = np.asarray(new_weights).flatten()
            return float(self.equity_rate * 0.05 * np.sum(np.maximum(0, cur - new)))

        cur = pd.Series(current_weights).reindex(prices.index, fill_value=0.0)
        new = pd.Series(new_weights).reindex(prices.index, fill_value=0.0)
        sell = (cur - new).clip(lower=0.0) * nav

        # Apply per-asset rate
        rates = pd.Series(self.equity_rate, index=prices.index)  # default
        for asset, klass in self.asset_classes.items():
            if asset not in rates.index:
                continue
            rates[asset] = {
                "equity": self.equity_rate,
                "fii": self.fii_rate,
                "bond": self.bond_rate,
                "foreign": self.foreign_rate,
            }.get(klass, self.equity_rate)

        # Simplified: assume gross sell amount is 5% gain (placeholder).
        # Real implementation needs cost-basis tracking.
        approx_gain = sell * 0.05
        total_tax = float((approx_gain * rates).sum())

        if total_tax <= self.monthly_threshold_brl and not self._is_day_trade(cur, new):
            total_tax = 0.0  # threshold exemption

        return total_tax / nav if nav > 0 else 0.0

    def _is_day_trade(self, cur, new) -> bool:
        # Placeholder; in reality this needs intraday tracking
        return False


# ---------------------------------------------------------------------------
# Composite cost
# ---------------------------------------------------------------------------

@dataclass
class CompositeCost:
    """Sum of multiple cost components. Useful for: brokerage + tax + FX."""

    components: list[CostModel] = field(default_factory=list)
    name: str = "composite"

    def cost(self, current_weights, new_weights, prices=None, nav=None, dt=None):
        return sum(
            c.cost(current_weights, new_weights, prices=prices, nav=nav, dt=dt)
            for c in self.components
        )


# ---------------------------------------------------------------------------
# Zero cost (testing)
# ---------------------------------------------------------------------------

@dataclass
class ZeroCost:
    """Zero-cost model. Useful for theoretical comparisons / unit tests."""

    name: str = "zero"

    def cost(self, current_weights, new_weights, prices=None, nav=None, dt=None):
        return 0.0


# ---------------------------------------------------------------------------
# Registry (for CLI / API access)
# ---------------------------------------------------------------------------

COST_MODELS: dict[str, type[CostModel]] = {
    "flat": FlatCost,
    "tiered": TieredCost,
    "b3": B3RealisticCost,
    "b3_realistic": B3RealisticCost,
    "offshore": OffshoreCost,
    "tax_aware": TaxAwareCost,
    "tax_aware_br": TaxAwareCost,
    "composite": CompositeCost,
    "zero": ZeroCost,
}


def get_cost_model(name: str, **kwargs) -> CostModel:
    """Instantiate a cost model by name."""
    key = name.lower()
    if key not in COST_MODELS:
        raise ValueError(f"Unknown cost model: {name!r}. Available: {list(COST_MODELS)}")
    return COST_MODELS[key](**kwargs)
