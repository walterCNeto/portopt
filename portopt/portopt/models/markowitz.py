"""Markowitz mean-variance optimization (Chagas §2).

Implements:
- Markowitz: full EF, either by target_return (min vol) or target_vol (max return)
- MinimumVariance: global minimum variance portfolio (MVP)
- MaximumSharpe: tangency portfolio (with risk-free asset)

Two backends:
- scipy: SLSQP (educational, mirrors Chagas' notebooks)
- cvxpy: production-grade convex QP
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.optimize as sco

from portopt.estimators import Moments, SampleCov, SampleMean, MeanEstimator, CovEstimator
from portopt.models.base import (
    Backend,
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
    build_scipy_constraints,
    initial_weights,
)


# ---------------------------------------------------------------------------
# Markowitz — general mean-variance optimization
# ---------------------------------------------------------------------------

class Markowitz(OptimizationModel):
    """Mean-Variance optimization (Markowitz 1952).

    Solves one of three equivalent formulations (Chagas §2.2):
    1. min vol(w) s.t. R_P(w) >= μ_target          (if target_return is set)
    2. max R_P(w) s.t. vol(w) <= σ_target          (if target_vol is set)
    3. min vol(w)                                   (default: MVP)

    Examples
    --------
    >>> model = Markowitz(backend="scipy")
    >>> result = model.fit(
    ...     returns,
    ...     ConstraintSet(bounds=(0.0, 0.40), target_return=0.0008),
    ... )
    """

    name = "markowitz"
    requires_returns = False  # we only need μ and Σ
    supports_short = True
    native_risk_measure = "vol"

    def __init__(
        self,
        backend: str = Backend.SCIPY,
        mean_estimator: MeanEstimator | None = None,
        cov_estimator: CovEstimator | None = None,
        tol: float = 1e-12,
    ):
        self.backend = backend
        self.mean_estimator = mean_estimator or SampleMean()
        self.cov_estimator = cov_estimator or SampleCov()
        self.tol = tol

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        moments = Moments.fit(returns, self.mean_estimator, self.cov_estimator)
        if self.backend == Backend.CVXPY:
            return self._fit_cvxpy(moments, returns.columns, constraints)
        return self._fit_scipy(moments, returns.columns, constraints)

    # ---------- SciPy SLSQP (educational, mirrors Chagas) ----------

    def _fit_scipy(
        self,
        moments: Moments,
        asset_names: pd.Index,
        constraints: ConstraintSet,
    ) -> OptimizationResult:
        N = moments.n_assets
        mu = moments.mean.flatten()
        cov = moments.cov

        x0 = initial_weights(N, "equal")
        bounds = constraints.get_bounds(N)

        # Decide on objective based on which target is set
        if constraints.target_vol is not None:
            # max R subject to vol <= tgt
            objective = lambda w: -float(mu @ w)
        else:
            # min vol [subject to R >= target_return, if any]
            objective = lambda w: float(w @ cov @ w)

        cons = build_scipy_constraints(
            constraints, mu=mu, cov=cov, asset_names=list(asset_names)
        )

        res = sco.minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            tol=self.tol,
            options={"maxiter": 5000},
        )

        w = pd.Series(res.x, index=asset_names)
        return OptimizationResult(
            weights=w,
            expected_return=float(mu @ res.x),
            risk=float(np.sqrt(max(res.x @ cov @ res.x, 0.0))),
            risk_measure="vol",
            converged=bool(res.success),
            diagnostics={
                "backend": "scipy_slsqp",
                "iterations": int(getattr(res, "nit", -1)),
                "message": str(res.message),
            },
            raw=res,
        )

    # ---------- cvxpy (production-grade QP) ----------

    def _fit_cvxpy(
        self,
        moments: Moments,
        asset_names: pd.Index,
        constraints: ConstraintSet,
    ) -> OptimizationResult:
        try:
            import cvxpy as cp
        except ImportError as e:
            raise ImportError("Install cvxpy: pip install cvxpy") from e

        N = moments.n_assets
        mu = moments.mean.flatten()
        cov = moments.cov

        w = cp.Variable(N)
        bounds = constraints.get_bounds(N)
        cons_cvx = [w >= np.array([b[0] for b in bounds]),
                    w <= np.array([b[1] for b in bounds])]

        if constraints.sum_to is not None:
            cons_cvx.append(cp.sum(w) == constraints.sum_to)

        if constraints.target_vol is not None:
            cons_cvx.append(cp.quad_form(w, cp.psd_wrap(cov)) <= constraints.target_vol ** 2)
            objective = cp.Maximize(mu @ w)
        else:
            if constraints.target_return is not None:
                cons_cvx.append(mu @ w >= constraints.target_return)
            objective = cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov)))

        prob = cp.Problem(objective, cons_cvx)
        prob.solve()

        w_val = np.array(w.value).flatten() if w.value is not None else np.full(N, np.nan)
        weights = pd.Series(w_val, index=asset_names)
        return OptimizationResult(
            weights=weights,
            expected_return=float(mu @ w_val) if not np.isnan(w_val).any() else None,
            risk=float(np.sqrt(max(w_val @ cov @ w_val, 0.0))) if not np.isnan(w_val).any() else float("nan"),
            risk_measure="vol",
            converged=prob.status == "optimal",
            diagnostics={"backend": "cvxpy", "status": prob.status},
            raw=prob,
        )


# ---------------------------------------------------------------------------
# Convenience subclasses
# ---------------------------------------------------------------------------

class MinimumVariance(Markowitz):
    """Global Minimum Variance Portfolio (no target return)."""

    name = "min_variance"

    def fit(self, returns, constraints, **kwargs):
        # Force no target_return so we get the MVP
        c2 = ConstraintSet(
            bounds=constraints.bounds,
            sum_to=constraints.sum_to,
            target_return=None,
            target_vol=None,
            group_bounds=constraints.group_bounds,
            asset_groups=constraints.asset_groups,
        )
        return super().fit(returns, c2, **kwargs)


class MaximumSharpe(Markowitz):
    """Tangency portfolio: maximizes Sharpe ratio (Chagas §2.4).

    Requires a risk-free rate (passed via `risk_free_rate`).
    Solves: max (μ - R_F)' w / sqrt(w' Σ w)
    """

    name = "max_sharpe"

    def __init__(self, risk_free_rate: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.risk_free_rate = risk_free_rate

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        moments = Moments.fit(returns, self.mean_estimator, self.cov_estimator)
        N = moments.n_assets
        mu = moments.mean.flatten()
        cov = moments.cov
        rf = self.risk_free_rate

        x0 = initial_weights(N, "equal")
        bounds = constraints.get_bounds(N)

        def neg_sharpe(w):
            ret = mu @ w - rf
            vol = np.sqrt(max(w @ cov @ w, 1e-12))
            return -ret / vol

        cons = []
        if constraints.sum_to is not None:
            cons.append({"type": "eq", "fun": lambda w: float(np.sum(w) - constraints.sum_to)})

        res = sco.minimize(
            neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=cons, tol=self.tol
        )

        w = pd.Series(res.x, index=returns.columns)
        port_ret = float(mu @ res.x)
        port_vol = float(np.sqrt(max(res.x @ cov @ res.x, 0.0)))
        sharpe = (port_ret - rf) / port_vol if port_vol > 0 else 0.0

        return OptimizationResult(
            weights=w,
            expected_return=port_ret,
            risk=port_vol,
            risk_measure="vol",
            converged=bool(res.success),
            diagnostics={"backend": "scipy_slsqp", "sharpe": sharpe, "rf": rf},
            raw=res,
        )
