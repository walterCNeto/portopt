"""Conditional Drawdown-at-Risk (Chekhlov-Uryasev-Zabarankin 2003, 2005)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


class CDaR(OptimizationModel):
    """Minimize Conditional Drawdown-at-Risk via LP formulation.

    CDaR_alpha is the expected drawdown over the alpha-worst portion of the
    drawdown distribution. Path-dependent risk measure suitable for managed
    accounts, hedge funds, and any strategy with drawdown limits.

    LP formulation (Chekhlov-Uryasev-Zabarankin 2005, Eq. 33-37):

        min  z + (1 / (T * alpha)) * sum_t u_t

        s.t. u_t >= y_t - V_t - z       (excess over VaR threshold)
             u_t >= 0
             y_t >= V_t                  (running max >= current)
             y_t >= y_{t-1}              (running max monotonic)
             y_0 >= 0
             V_t = sum_{s<=t} (R[s,:] @ omega)
             sum(omega) = 1
             omega in [lb, ub]

    Variables: omega (N) + z (1) + u (T) + y (T). V_t is pre-computed as a
    linear function of omega via the cumulative returns matrix M, where
    M[t, i] = sum_{s<=t} R[s, i]. Then V_t = M[t, :] @ omega.

    Final formulation has N + 1 + 2T variables and ~3T inequalities + 1
    equality. Solved with linprog HiGHS (fast and reliable for sparse LPs).
    """

    name = "cdar"
    native_risk_measure = "cdar"
    requires_returns = True
    supports_short = False

    def __init__(self, alpha: float = 0.05, backend: str = "linprog"):
        if not (0 < alpha < 1):
            raise ValueError(f"alpha must be in (0,1), got {alpha}")
        self.alpha = alpha
        self.backend = backend

    def fit(self, log_returns, constraints=None):
        constraints = constraints or ConstraintSet()
        T, N = log_returns.shape
        names = list(log_returns.columns)
        R = log_returns.values

        lb, ub = constraints.bounds
        sum_to = constraints.sum_to or 1.0

        # Pre-compute cumulative returns matrix: M[t, i] = sum_{s<=t} R[s, i]
        M = np.cumsum(R, axis=0)

        # Variable layout: [omega (N) | z (1) | u (T) | y (T)]
        off_omega = 0
        off_z = N
        off_u = N + 1
        off_y = N + 1 + T
        n_total = N + 1 + 2 * T

        # Objective: c^T x = z + (1/(T*alpha)) * sum(u_t)
        c = np.zeros(n_total)
        c[off_z] = 1.0
        c[off_u:off_u + T] = 1.0 / (T * self.alpha)

        # Inequalities: 3T constraints
        # (1) -M[t,:] @ omega - z - u_t + y_t <= 0   (u_t >= y_t - V_t - z)
        # (2)  M[t,:] @ omega - y_t <= 0              (y_t >= V_t)
        # (3) -y_t + y_{t-1} <= 0  for t >= 1         (y monotonic)
        A_ub = np.zeros((3 * T, n_total))

        for t in range(T):
            # (1)
            A_ub[t, off_omega:off_omega + N] = -M[t, :]
            A_ub[t, off_z] = -1.0
            A_ub[t, off_u + t] = -1.0
            A_ub[t, off_y + t] = 1.0

            # (2)
            A_ub[T + t, off_omega:off_omega + N] = M[t, :]
            A_ub[T + t, off_y + t] = -1.0

        for t in range(1, T):
            # (3)
            A_ub[2 * T + t, off_y + t] = -1.0
            A_ub[2 * T + t, off_y + t - 1] = 1.0
        # Row 2T+0 is all zeros (no y_{-1}); trivially satisfied.

        b_ub = np.zeros(3 * T)

        # Equality: sum(omega) = sum_to
        A_eq = np.zeros((1, n_total))
        A_eq[0, off_omega:off_omega + N] = 1.0
        b_eq = np.array([sum_to])

        # Bounds
        bounds = []
        for _ in range(N):
            bounds.append((lb, ub))
        bounds.append((None, None))   # z free
        for _ in range(T):
            bounds.append((0.0, None))  # u_t >= 0
        for _ in range(T):
            bounds.append((0.0, None))  # y_t >= 0

        res = linprog(
            c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
            bounds=bounds, method="highs",
        )

        if not res.success:
            raise RuntimeError(f"CDaR linprog failed: {res.message}")

        x = res.x
        omega = x[off_omega:off_omega + N]
        z_star = float(x[off_z])
        u_t = x[off_u:off_u + T]
        y_t = x[off_y:off_y + T]
        V_t = M @ omega

        cdar = float(z_star + np.sum(u_t) / (T * self.alpha))
        mu = R.mean(axis=0)
        expected_log_ret = float(omega @ mu)
        max_drawdown_realized = float(np.max(y_t - V_t))

        return OptimizationResult(
            weights={n: float(w) for n, w in zip(names, omega)},
            expected_return=expected_log_ret,
            risk=cdar,
            risk_measure="cdar",
            converged=bool(res.success),
            diagnostics={
                "backend": "linprog_highs",
                "iterations": int(getattr(res, "nit", -1)),
                "message": str(res.message),
                "alpha": self.alpha,
                "z_star": z_star,
                "max_drawdown_realized": max_drawdown_realized,
                "T": T,
                "N": N,
            },
        )
