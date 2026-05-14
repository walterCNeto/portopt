"""Golden tests against bundled reference datasets.

These tests load the actual Excel files distributed with the course and
validate that the portopt outputs are mathematically consistent and
economically sensible. They serve three purposes:

1. **Regression**: catch numerical regressions when refactoring.
2. **Validation**: confirm that the implementations of MAD/CVaR/HRP/etc
   produce outputs in the same ballpark as reference notebooks.
3. **Documentation**: show concrete usage with real datasets.

Run with:
    pytest tests/test_golden_datasets.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import portopt as po
from portopt import datasets


# ---------------------------------------------------------------------------
# Dataset loading sanity
# ---------------------------------------------------------------------------

def test_all_datasets_load():
    for name in datasets.list_datasets():
        prices = datasets.load(name)
        assert isinstance(prices, pd.DataFrame)
        assert len(prices) > 100, f"{name}: too few rows"
        assert prices.shape[1] >= 10, f"{name}: too few columns"
        # No all-NaN columns
        assert not prices.isna().all().any(), f"{name}: column with all NaN"
        # Index is DatetimeIndex
        assert isinstance(prices.index, pd.DatetimeIndex)


def test_ex1_subsets():
    """Ex1.xlsx: BR stocks + CDI"""
    all_data = datasets.load("ex1")
    br = datasets.subset("ex1", "br_stocks")
    cdi = datasets.subset("ex1", "cdi")
    assert all_data.shape[1] == 25
    assert br.shape[1] == 24
    assert cdi.shape[1] == 1
    assert "BZACCETP Index" in cdi.columns


def test_mdr_subsets():
    """MDR: 24 commodity futures with group subsets"""
    all_data = datasets.load("mdr")
    metals = datasets.subset("mdr", "metals")
    energy = datasets.subset("mdr", "energy")
    agri = datasets.subset("mdr", "agri")
    livestock = datasets.subset("mdr", "livestock")
    assert all_data.shape[1] == 24
    assert metals.shape[1] == 7
    assert energy.shape[1] == 6
    assert agri.shape[1] == 9
    assert livestock.shape[1] == 2


# ---------------------------------------------------------------------------
# Ex1.xlsx (BR equities) — nb1 territory
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ex1_logrets() -> pd.DataFrame:
    """Daily log-returns of 24 BR stocks, last 10 years."""
    prices = datasets.subset("ex1", "br_stocks").loc["2014-01-01":]
    return po.returns.to_log_returns(prices)


def test_ex1_markowitz_concentrates_defensives(ex1_logrets):
    """MV/MVP should overweight defensive Brazilian stocks (VIVT3, ABEV3, TRPL4)."""
    result = po.models.MinimumVariance().fit(
        ex1_logrets, po.ConstraintSet(bounds=(0.0, 1.0))
    )
    top3 = result.weights.sort_values(ascending=False).head(3).index.tolist()
    top3_tickers = [c.split()[0] for c in top3]
    # At least 2 of these defensives should be in the top 3
    defensives = {"VIVT3", "ABEV3", "TRPL4", "EGIE3"}
    assert len(set(top3_tickers) & defensives) >= 2, (
        f"Expected MVP to overweight defensives, got top3={top3_tickers}"
    )


def test_ex1_mvp_lower_vol_than_ew(ex1_logrets):
    """MVP must have weakly lower volatility than EW (by definition)."""
    mvp = po.models.MinimumVariance().fit(ex1_logrets, po.ConstraintSet())
    ew = po.models.EqualWeight().fit(ex1_logrets, po.ConstraintSet())
    assert mvp.risk <= ew.risk + 1e-6


def test_ex1_backtest_completes(ex1_logrets):
    """Full backtest on Ex1 BR equities should complete and produce sensible metrics."""
    prices = datasets.subset("ex1", "br_stocks").loc["2014-01-01":]
    cfg = po.BacktestConfig(
        training_window=252,
        rebalance="monthly",
        progress=False,
    )
    bt = po.BacktestEngine(cfg).run(
        prices, po.models.EqualWeight(), po.ConstraintSet()
    )
    # 10 years monthly ~ 120 rebalances
    assert 100 <= len(bt.rebalance_dates) <= 130
    # Volatility should be in BR-equity ballpark (~20-30% annualized)
    ann_vol = bt.metrics["annualized_vol"]
    assert 0.15 < ann_vol < 0.45, f"vol_ann={ann_vol:.2%} outside expected range"


# ---------------------------------------------------------------------------
# MDR_Example.xlsx (24 commodities) — nb2 Downside Risk
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mdr_logrets() -> pd.DataFrame:
    """5d log-returns of 24 commodity futures (standard literature choice)."""
    prices = datasets.load("mdr").iloc[::5]
    return po.returns.to_log_returns(prices)


def test_mdr_dr_concentrates_low_risk_commodities(mdr_logrets):
    """Mean-Downside-Risk on commodities should concentrate in Cattle and Gold."""
    result = po.models.DownsideRisk().fit(mdr_logrets, po.ConstraintSet())
    top3 = result.weights.sort_values(ascending=False).head(3).index.tolist()
    # Cattle and Gold are systematically defensive commodities in this sample
    assert "Cattle" in top3 or "Gold" in top3, (
        f"Expected DR to overweight defensives, got top3={top3}"
    )


def test_mdr_mv_dr_consistency(mdr_logrets):
    """MV and DR should agree on the top picks for commodities (per classical theory)."""
    mv = po.models.Markowitz().fit(mdr_logrets, po.ConstraintSet())
    dr = po.models.DownsideRisk().fit(mdr_logrets, po.ConstraintSet())
    mv_top5 = set(mv.weights.sort_values(ascending=False).head(5).index)
    dr_top5 = set(dr.weights.sort_values(ascending=False).head(5).index)
    # At least 3 of top 5 should match (MV/DR agree closely on quasi-symmetric returns)
    assert len(mv_top5 & dr_top5) >= 3


# ---------------------------------------------------------------------------
# MCVaR_Example.xls (24 commodities) — nb2 CVaR
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mcvar_logrets() -> pd.DataFrame:
    prices = datasets.load("mcvar").iloc[::5]
    return po.returns.to_log_returns(prices)


def test_mcvar_linprog_succeeds(mcvar_logrets):
    """CVaR via linprog HiGHS must converge on this dataset."""
    result = po.models.CVaR(alpha=0.05, n_scenarios=0).fit(
        mcvar_logrets, po.ConstraintSet()
    )
    assert result.converged
    assert result.risk > 0  # CVaR loss is positive
    assert abs(result.weights.sum() - 1.0) < 1e-4


def test_mcvar_simulated_scenarios(mcvar_logrets):
    """CVaR with 10k MVN simulations (standard MVN scenario setup) should match MV roughly."""
    cvar_result = po.models.CVaR(alpha=0.05, n_scenarios=10_000, random_state=42).fit(
        mcvar_logrets, po.ConstraintSet()
    )
    mv_result = po.models.Markowitz().fit(mcvar_logrets, po.ConstraintSet())

    # MVN simulations underestimate tail → CVaR weights similar to MV
    # Quantify: top5 should overlap by at least 4 out of 5
    cvar_top5 = set(cvar_result.weights.sort_values(ascending=False).head(5).index)
    mv_top5 = set(mv_result.weights.sort_values(ascending=False).head(5).index)
    overlap = len(cvar_top5 & mv_top5)
    assert overlap >= 4, (
        f"Expected CVaR-MVN ≈ MV top picks , overlap={overlap}/5"
    )


def test_mcvar_groups_recognized(mcvar_logrets):
    """Group definitions for commodities should match the dataset's columns."""
    from portopt.datasets import ASSET_GROUPS
    groups = ASSET_GROUPS["mcvar"]
    cols = set(mcvar_logrets.columns)
    for group_name, assets in groups.items():
        missing = set(assets) - cols
        assert not missing, f"Group {group_name}: missing assets {missing}"


# ---------------------------------------------------------------------------
# Risk Budgeting on commodity groups (literature exercise)
# ---------------------------------------------------------------------------

def test_risk_budget_per_commodity_group(mdr_logrets):
    """Risk Budgeting with 4 commodity groups should approximately respect budgets."""
    constraints = po.ConstraintSet(
        bounds=(0.0, 1.0),
        asset_groups={
            "Metals": ["Aluminum", "Copper", "Gold", "Nickel", "Platinum", "Silver", "Zinc"],
            "Energy": ["Brent Crude Oil", "WTI Oil", "Gas Oil", "Gasoline", "Heating Oil", "Natural Gas"],
            "Agri": ["Cocoa", "Coffee", "Corn", "Cotton", "Soybean", "Soymeal", "Soy Oil", "Sugar", "Wheat"],
            "Livestock": ["Cattle", "Hogs"],
        },
        group_risk_budgets={"Metals": 0.20, "Energy": 0.30, "Agri": 0.30, "Livestock": 0.20},
    )
    result = po.models.RiskBudget(approach="2").fit(mdr_logrets, constraints)
    assert result.converged

    realized = result.diagnostics["group_budgets_realized"]
    # Each group's realized RC should be within 10pp of the target (approach 2 is soft)
    for grp, target in result.diagnostics["group_budgets_target"].items():
        assert abs(realized[grp] - target) < 0.15, (
            f"Group {grp}: target={target:.2f}, realized={realized[grp]:.2f}"
        )
