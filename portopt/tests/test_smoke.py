"""Smoke tests + invariants for portopt.

Validates that every model and every cost function works end-to-end.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import portopt as po
from portopt.models import MODEL_REGISTRY, get_model, list_models


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_returns() -> pd.DataFrame:
    """Reproducible synthetic returns for testing (5 assets, ~3y daily)."""
    np.random.seed(42)
    T, N = 800, 5
    names = ["A", "B", "C", "D", "E"]
    mu_true = np.array([0.0005, 0.0007, 0.0006, 0.0002, 0.0003])
    chol = np.random.randn(N, N) * 0.005
    sigma = chol @ chol.T + np.diag([0.010, 0.014, 0.013, 0.008, 0.007]) ** 2
    rets = np.random.multivariate_normal(mu_true, sigma, size=T)
    return pd.DataFrame(
        rets, columns=names,
        index=pd.date_range("2021-01-01", periods=T, freq="B"),
    )


@pytest.fixture(scope="module")
def synthetic_prices(synthetic_returns) -> pd.DataFrame:
    return np.exp(synthetic_returns.cumsum())


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_resolves_all_aliases():
    for alias in MODEL_REGISTRY:
        # Some models require positional args; skip those that need them
        try:
            get_model(alias)
        except TypeError:
            pass  # BL needs market_weights, delta, P, Q


def test_list_models_returns_unique():
    names = list_models()
    assert len(names) == len(set(names))
    assert len(names) >= 16


# ---------------------------------------------------------------------------
# Smoke test all models
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model_name", [
    "ew", "iv", "markowitz", "min_var", "mad", "erc", "hrp",
    "cvar", "utility", "downside_risk",
])
def test_model_fit_smoke(synthetic_returns, model_name):
    """Every model should produce: valid weights summing to ~1, finite risk."""
    model = get_model(model_name)
    result = model.fit(synthetic_returns, po.ConstraintSet())

    w = result.weights.values
    assert len(w) == synthetic_returns.shape[1]
    assert np.all(np.isfinite(w))
    assert abs(w.sum() - 1.0) < 1e-4, f"Weights don't sum to 1: {w.sum()}"
    assert np.isfinite(result.risk)
    assert result.risk >= 0


# ---------------------------------------------------------------------------
# Mathematical invariants
# ---------------------------------------------------------------------------

def test_equal_weight_invariant(synthetic_returns):
    """EW should yield exactly 1/N for each asset."""
    result = po.models.EqualWeight().fit(synthetic_returns, po.ConstraintSet())
    N = synthetic_returns.shape[1]
    np.testing.assert_allclose(result.weights.values, np.full(N, 1.0 / N))


def test_erc_invariant_risk_contributions_balanced(synthetic_returns):
    """ERC: risk contributions should be approximately equal."""
    result = po.models.EqualRiskContribution().fit(
        synthetic_returns, po.ConstraintSet()
    )
    rc_pct = result.diagnostics["rc_pct"]
    N = len(rc_pct)
    # Each RC should be close to 1/N
    for rc in rc_pct:
        assert abs(rc - 1.0 / N) < 0.05, f"RC = {rc} not balanced"


def test_inverse_vol_invariant(synthetic_returns):
    """IV: weights should be proportional to 1/sigma."""
    result = po.models.InverseVolatility().fit(synthetic_returns, po.ConstraintSet())
    vols = synthetic_returns.std().values
    expected = (1.0 / vols) / (1.0 / vols).sum()
    np.testing.assert_allclose(result.weights.values, expected, rtol=1e-3)


def test_mad_consistency(synthetic_returns):
    """MAD model risk should be a sensible MAD value > 0."""
    result = po.models.MAD().fit(synthetic_returns, po.ConstraintSet())
    assert result.risk > 0
    # MAD <= vol*sqrt(2/pi) for symmetric distributions (loose bound)
    vols = synthetic_returns.std().values
    assert result.risk < vols.max() * 2


def test_markowitz_min_var_below_ew_vol(synthetic_returns):
    """MVP should have ≤ vol of EW (by construction)."""
    mvp = po.models.MinimumVariance().fit(synthetic_returns, po.ConstraintSet())
    ew = po.models.EqualWeight().fit(synthetic_returns, po.ConstraintSet())
    assert mvp.risk <= ew.risk + 1e-4


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def test_bounds_are_respected(synthetic_returns):
    """All models should respect (0, 0.5) bounds."""
    constraints = po.ConstraintSet(bounds=(0.0, 0.5))
    for name in ["markowitz", "mad", "erc", "hrp"]:
        result = get_model(name).fit(synthetic_returns, constraints)
        w = result.weights.values
        assert (w >= -1e-4).all(), f"{name}: negative weight found: {w}"
        assert (w <= 0.5 + 1e-4).all(), f"{name}: weight exceeds 0.5: {w.max()}"


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

def test_backtest_completes(synthetic_returns, synthetic_prices):
    """Engine should run without errors and produce coherent output."""
    cfg = po.BacktestConfig(training_window=252, rebalance="monthly", progress=False)
    engine = po.BacktestEngine(cfg)
    result = engine.run(synthetic_prices, po.models.EqualWeight(), po.ConstraintSet())

    assert len(result.log_returns) > 0
    assert len(result.rebalance_dates) > 0
    assert len(result.weights) == len(result.log_returns)
    # Cumulative wealth monotonic in time (just check it's finite)
    assert result.cumulative_wealth.iloc[-1] > 0


def test_backtest_costs_reduce_wealth(synthetic_returns, synthetic_prices):
    """A positive cost model should yield strictly lower terminal wealth."""
    from portopt.costs import FlatCost, ZeroCost

    cfg_zero = po.BacktestConfig(
        training_window=252, rebalance="monthly",
        transaction_costs=ZeroCost(), progress=False,
    )
    cfg_cost = po.BacktestConfig(
        training_window=252, rebalance="monthly",
        transaction_costs=FlatCost(rate=0.005), progress=False,  # 50 bps, exaggerated
    )

    bt_zero = po.BacktestEngine(cfg_zero).run(
        synthetic_prices, po.models.Markowitz(), po.ConstraintSet()
    )
    bt_cost = po.BacktestEngine(cfg_cost).run(
        synthetic_prices, po.models.Markowitz(), po.ConstraintSet()
    )
    assert bt_zero.cumulative_wealth.iloc[-1] >= bt_cost.cumulative_wealth.iloc[-1]


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

def test_compare_produces_tables(synthetic_returns, synthetic_prices):
    result = po.compare(
        models=["ew", "markowitz", "hrp"],
        prices=synthetic_prices,
        constraints=po.ConstraintSet(),
    )
    summary = result.summary_table()
    assert len(summary) == 3
    assert "expected_return" in summary.columns
    assert "risk" in summary.columns

    weights = result.weights_table()
    assert weights.shape == (synthetic_returns.shape[1], 3)


# ---------------------------------------------------------------------------
# Cost models
# ---------------------------------------------------------------------------

def test_all_cost_models_return_nonneg():
    from portopt.costs import COST_MODELS
    w1 = np.array([0.2] * 5)
    w2 = np.array([0.1, 0.3, 0.2, 0.2, 0.2])
    for name, cls in COST_MODELS.items():
        # Some need explicit kwargs
        try:
            model = cls()
        except TypeError:
            continue
        c = model.cost(w1, w2)
        assert c >= 0, f"{name}: returned negative cost {c}"


# ---------------------------------------------------------------------------
# Risk measures
# ---------------------------------------------------------------------------

def test_risk_contribs_sum_to_vol(synthetic_returns):
    """Euler's theorem: Σ RC_i = vol_P."""
    from portopt.risk_measures import volatility, risk_contrib
    w = np.array([0.2] * 5)
    cov = synthetic_returns.cov().values
    rc = risk_contrib(w, cov)
    vol = volatility(w, cov)
    assert abs(rc.sum() - vol) < 1e-10


# ============================================================================
# TrackingError tests (Phase 2)
# ============================================================================

def test_tracking_error_minimization_stays_near_benchmark():
    """Pure TE minimization (no return target) should track benchmark."""
    import numpy as np
    import pandas as pd
    from portopt.models.tracking import TrackingError
    from portopt.models.base import ConstraintSet

    rng = np.random.default_rng(42)
    T, N = 500, 5
    R = pd.DataFrame(
        rng.standard_normal((T, N)) * 0.01,
        columns=[f"asset_{i}" for i in range(N)],
    )
    omega_B = np.array([0.4, 0.3, 0.2, 0.05, 0.05])

    model = TrackingError()
    cons = ConstraintSet(bounds=(0.0, 1.0), benchmark_weights=omega_B)
    result = model.fit(R, cons)

    assert result.converged
    omega = np.array(list(result.weights.values()))
    assert abs(omega.sum() - 1.0) < 1e-4
    # Should be very close to benchmark (low TE)
    assert np.max(np.abs(omega - omega_B)) < 0.10
    assert result.risk >= 0.0


def test_tracking_error_with_target_seeks_excess_return():
    """With target_te budget, optimizer should deviate from benchmark to gain excess return."""
    import numpy as np
    import pandas as pd
    from portopt.models.tracking import TrackingError
    from portopt.models.base import ConstraintSet

    rng = np.random.default_rng(7)
    T, N = 300, 4
    base = rng.standard_normal((T, N)) * 0.01
    # Make asset 0 strictly dominant in mean
    base[:, 0] += 0.005
    R = pd.DataFrame(base, columns=[f"asset_{i}" for i in range(N)])
    omega_B = np.array([0.25, 0.25, 0.25, 0.25])

    model = TrackingError(target_te=0.005)
    cons = ConstraintSet(bounds=(0.0, 1.0), benchmark_weights=omega_B)
    result = model.fit(R, cons)

    assert result.converged
    # Should overweight asset 0 (dominant returns)
    assert result.weights["asset_0"] > 0.25


# ============================================================================
# CDaR tests (Phase 2)
# ============================================================================

def test_cdar_produces_valid_portfolio():
    """CDaR LP should solve and produce valid weights."""
    import numpy as np
    import pandas as pd
    from portopt.models.cdar import CDaR

    rng = np.random.default_rng(0)
    T, N = 250, 5
    R = pd.DataFrame(
        rng.standard_normal((T, N)) * 0.01,
        columns=[f"asset_{i}" for i in range(N)],
    )

    model = CDaR(alpha=0.05)
    result = model.fit(R)

    assert result.converged
    omega = np.array(list(result.weights.values()))
    assert abs(omega.sum() - 1.0) < 1e-4
    assert all(w >= -1e-6 for w in omega)
    assert result.risk_measure == "cdar"
    assert result.risk >= 0.0


def test_cdar_avoids_high_drawdown_asset():
    """CDaR should underweight assets with severe historical drawdowns."""
    import numpy as np
    import pandas as pd
    from portopt.models.cdar import CDaR

    rng = np.random.default_rng(42)
    T = 500
    # asset "stable": low vol, no drawdown
    stable = rng.standard_normal(T) * 0.005
    # asset "crashes": severe sustained loss in first half
    crashes = np.concatenate([
        np.full(T // 4, -0.02),
        rng.standard_normal(T - T // 4) * 0.01,
    ])
    R = pd.DataFrame({"stable": stable, "crashes": crashes})

    model = CDaR(alpha=0.05)
    result = model.fit(R)

    assert result.converged
    # CDaR should heavily favor the stable asset
    assert result.weights["stable"] > result.weights["crashes"]
