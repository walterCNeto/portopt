"""Equal Risk Contribution / Risk Parity (Maillard-Roncalli-Teiletche 2010).

Seeks weights such that each asset contributes equally to portfolio volatility:
    RC_i = vol_P / N  ∀ i

Formulation:
    min Σ_i (w_i * (Σw)_i / vol_target² - 1/N)²
    s.t.  Σ w_i = 1,  w_i >= 0,  w' Σ w = vol_target²
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import scipy.optimize as sco

from portopt.estimators import EWMACov, SampleCov, CovEstimator
from portopt.models.base import (
    Backend,
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)
from portopt.models.naive import InverseVolatility


class EqualRiskContribution(OptimizationModel):
    """ERC / Risk Parity portfolio.

    Parameters
    ----------
    cov_estimator : CovEstimator, optional
        Default: SampleCov. EWMACov(halflife=63) is a common alternative in the literature.
    warm_start : "iv" or "equal"
        Initial point for SLSQP. ERC is known to have multiple local
        minima; warm-starting from IV greatly improves convergence (nb3 §4.5).
    target_vol : float, optional
        If set, vol_P = target_vol (requires cash/leverage). If None, no
        absolute volatility constraint and the portfolio is just normalized.
    """

    name = "erc"
    requires_returns = False
    supports_short = False
    native_risk_measure = "vol"

    def __init__(
        self,
        cov_estimator: Optional[CovEstimator] = None,
        warm_start: str = "iv",
        tol: float = 1e-12,
        maxiter: int = 5000,
    ):
        self.cov_estimator = cov_estimator or SampleCov()
        self.warm_start = warm_start
        self.tol = tol
        self.maxiter = maxiter

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        cov = self.cov_estimator.fit(returns)
        N = cov.shape[0]

        # Warm start
        if self.warm_start == "iv":
            iv_res = InverseVolatility().fit(returns, constraints)
            w0 = iv_res.weights.values
        else:
            w0 = np.ones(N) / N

        # Objective
        target_var = (constraints.target_vol ** 2) if constraints.target_vol else None

        def objective(w):
            Ew = cov @ w
            if target_var is not None:
                # ERC vs target volatility
                return float(np.sum((w * Ew / target_var - 1.0 / N) ** 2))
            else:
                varp = float(w @ cov @ w)
                if varp <= 0:
                    return 1e6
                return float(np.sum((w * Ew / varp - 1.0 / N) ** 2))

        cons = []
        if constraints.sum_to is not None:
            cons.append({"type": "eq", "fun": lambda w: float(np.sum(w) - constraints.sum_to)})
        if target_var is not None:
            cons.append({"type": "eq", "fun": lambda w: float(w @ cov @ w - target_var)})

        bounds = constraints.get_bounds(N)

        res = sco.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            tol=self.tol,
            options={"maxiter": self.maxiter},
        )

        w_opt = res.x
        vol = float(np.sqrt(max(w_opt @ cov @ w_opt, 0.0)))
        port_ret = float(returns.mean().values @ w_opt)

        # Diagnostic: RC dispersion (should be ~0 if perfectly balanced)
        Ew = cov @ w_opt
        rc = w_opt * Ew / vol if vol > 0 else np.zeros(N)
        rc_pct = rc / rc.sum() if rc.sum() > 0 else rc

        return OptimizationResult(
            weights=pd.Series(w_opt, index=returns.columns),
            expected_return=port_ret,
            risk=vol,
            risk_measure="vol",
            converged=bool(res.success),
            diagnostics={
                "backend": "scipy_slsqp",
                "warm_start": self.warm_start,
                "rc_pct": rc_pct.tolist(),
                "rc_dispersion": float(np.std(rc_pct)),
                "message": str(res.message),
            },
            raw=res,
        )
