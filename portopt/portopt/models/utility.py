"""Quadratic Utility optimization .

Solves: max  μ'w - 0.5 λ w' Σ w
        s.t. constraints

TODO: implement (similar to Markowitz but with explicit utility objective).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.optimize as sco

from portopt.estimators import Moments, SampleCov, SampleMean
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
    build_scipy_constraints,
    initial_weights,
)


class QuadraticUtility(OptimizationModel):
    """Quadratic utility maximizer: max μ'w - 0.5 λ w'Σw."""

    name = "utility"
    requires_returns = False
    supports_short = True
    native_risk_measure = "vol"

    def __init__(self, risk_aversion: float = 1.0):
        self.risk_aversion = risk_aversion

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        moments = Moments.fit(returns, SampleMean(), SampleCov())
        N = moments.n_assets
        mu = moments.mean.flatten()
        cov = moments.cov
        lam = constraints.risk_aversion or self.risk_aversion

        objective = lambda w: -(mu @ w - 0.5 * lam * (w @ cov @ w))

        x0 = initial_weights(N, "equal")
        bounds = constraints.get_bounds(N)
        cons = build_scipy_constraints(constraints, mu=mu, cov=cov)

        res = sco.minimize(
            objective, x0, method="SLSQP", bounds=bounds, constraints=cons, tol=1e-12
        )

        w = pd.Series(res.x, index=returns.columns)
        return OptimizationResult(
            weights=w,
            expected_return=float(mu @ res.x),
            risk=float(np.sqrt(max(res.x @ cov @ res.x, 0.0))),
            risk_measure="vol",
            converged=bool(res.success),
            diagnostics={"backend": "scipy_slsqp", "lambda": lam},
            raw=res,
        )
