"""Downside Risk optimization (Sortino-Meer 1991).

TODO: implement (similar to Markowitz but with downside risk as objective).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.optimize as sco

from portopt.models.base import (
    ConstraintSet, OptimizationModel, OptimizationResult,
    build_scipy_constraints, initial_weights,
)


class DownsideRisk(OptimizationModel):
    """Mean-Downside-Risk portfolio optimizer."""

    name = "downside_risk"
    requires_returns = True
    supports_short = False
    native_risk_measure = "downside_risk"

    def __init__(self, mar: float = 0.0):
        self.mar = mar

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        R = returns.values
        T, N = R.shape
        mu = R.mean(axis=0)

        def objective(w):
            port_rets = R @ w
            downside = np.minimum(port_rets - self.mar, 0.0)
            return float(np.mean(downside ** 2))

        x0 = initial_weights(N, "equal")
        bounds = constraints.get_bounds(N)
        cons = build_scipy_constraints(constraints, mu=mu)

        res = sco.minimize(
            objective, x0, method="SLSQP", bounds=bounds, constraints=cons, tol=1e-12
        )

        w_opt = res.x
        dr = float(np.sqrt(objective(w_opt)))

        return OptimizationResult(
            weights=pd.Series(w_opt, index=returns.columns),
            expected_return=float(mu @ w_opt),
            risk=dr,
            risk_measure="downside_risk",
            converged=bool(res.success),
            diagnostics={"backend": "scipy_slsqp", "mar": self.mar},
            raw=res,
        )
