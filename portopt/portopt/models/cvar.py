"""Mean-CVaR optimization (Rockafellar-Uryasev 2000).

Decision variables: x = [w_1, ..., w_N, VaR, u_1, ..., u_S]   length N + 1 + S

Linearized as:
    min  VaR + (1/(S·α)) Σ u_s
    s.t. u_s + r_s' w + VaR >= 0   for s = 1..S
         Σ w_i = 1
         u_s >= 0
         μ' w >= μ_target  (optional)

Solved via scipy.optimize.linprog (HiGHS), as recommended in classical references.

TODO: complete implementation following nb2 cell 83.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.optimize as sco

from portopt.models.base import (
    Backend,
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


class CVaR(OptimizationModel):
    """Mean-CVaR portfolio optimizer.

    Parameters
    ----------
    alpha : float
        Significance level. Default 0.05 (95% CVaR).
    n_scenarios : int
        If positive, simulate this many scenarios using multivariate normal
        with the sample μ, Σ. If 0, use the historical returns directly.
    backend : Backend
        Only LINPROG supported (SLSQP is unreliable for CVaR, per the literature).
    """

    name = "cvar"
    requires_returns = True
    supports_short = False
    native_risk_measure = "cvar"

    def __init__(
        self,
        alpha: float = 0.05,
        n_scenarios: int = 0,
        backend: str = Backend.LINPROG,
        random_state: int | None = 42,
    ):
        if backend == Backend.SCIPY:
            raise ValueError("CVaR with SLSQP is unreliable for this LP formulation. Use LINPROG.")
        self.alpha = alpha
        self.n_scenarios = n_scenarios
        self.backend = backend
        self.random_state = random_state

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        N = returns.shape[1]
        mu = returns.mean().values

        # Build scenarios
        if self.n_scenarios > 0:
            cov = returns.cov().values
            rng = np.random.default_rng(self.random_state)
            scenarios = rng.multivariate_normal(mu, cov, size=self.n_scenarios)
        else:
            scenarios = returns.values

        S = len(scenarios)
        n_var = N + 1 + S
        alpha = self.alpha

        # c = [0...0, 1, 1/(Sα),...,1/(Sα)]
        c = np.concatenate([np.zeros(N), [1.0], np.full(S, 1.0 / (S * alpha))])

        # Inequality: -r_s' w - VaR - u_s <= 0
        A_ub = np.zeros((S, n_var))
        for s in range(S):
            A_ub[s, :N] = -scenarios[s]
            A_ub[s, N] = -1.0
            A_ub[s, N + 1 + s] = -1.0
        b_ub = np.zeros(S)

        # Target return: -μ' w <= -tgt
        if constraints.target_return is not None:
            new_row = np.concatenate([-mu, np.zeros(1 + S)])
            A_ub = np.vstack([A_ub, new_row])
            b_ub = np.append(b_ub, -constraints.target_return)

        # Sum-to-one
        A_eq = np.zeros((1, n_var))
        A_eq[0, :N] = 1.0
        b_eq = np.array([constraints.sum_to or 1.0])

        # Bounds
        w_bounds = constraints.get_bounds(N)
        bounds = w_bounds + [(0.0, None)] + [(0.0, None)] * S  # VaR >= 0, u_s >= 0

        res = sco.linprog(
            c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
            bounds=bounds, method="highs",
        )

        if not res.success:
            return OptimizationResult(
                weights=pd.Series(np.full(N, np.nan), index=returns.columns),
                expected_return=None,
                risk=float("nan"),
                risk_measure="cvar",
                converged=False,
                diagnostics={"backend": "linprog_highs", "message": res.message},
                raw=res,
            )

        w_opt = res.x[:N]
        var_value = res.x[N]
        cvar_value = float(res.fun)

        return OptimizationResult(
            weights=pd.Series(w_opt, index=returns.columns),
            expected_return=float(mu @ w_opt),
            risk=cvar_value,
            risk_measure="cvar",
            converged=True,
            diagnostics={
                "backend": "linprog_highs",
                "alpha": alpha,
                "n_scenarios": S,
                "var": var_value,
            },
            raw=res,
        )
