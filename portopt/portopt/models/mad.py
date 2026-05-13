"""Mean-Absolute Deviation optimization (Konno-Yamazaki 1991, Chagas §3.2).

Linearizes the MAD problem using auxiliary variables y_t, z_t >= 0 such that
y_t - z_t = Σ_i (r_{t,i} - μ_i) w_i. Then |·| = y_t + z_t and we minimize sum.

Solved via scipy.optimize.linprog (HiGHS) which is dramatically faster than SLSQP.
Chagas demonstrates the speedup empirically in nb2.
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


class MAD(OptimizationModel):
    """Mean-MAD optimization.

    Decision variables: x = [w_1, ..., w_N, y_1, ..., y_T, z_1, ..., z_T]
    Total dimension: N + 2T.

    Objective: min Σ (y_t + z_t)

    Equality constraints:
    - Σ w_i = 1                                (1 equation)
    - y_t - z_t = Σ_i (r_{t,i} - μ_i) w_i      (T equations)

    Inequality constraints:
    - μ' w >= target_return  =>  -μ' w <= -target_return
    """

    name = "mad"
    requires_returns = True
    supports_short = True
    native_risk_measure = "mad"

    def __init__(self, backend: str = Backend.LINPROG):
        if backend == Backend.SCIPY:
            raise ValueError(
                "MAD with SLSQP is unreliable per Chagas §3.2 (nb2 cell 32). "
                "Use Backend.LINPROG."
            )
        self.backend = backend

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        R = returns.values  # T x N
        T, N = R.shape
        mu = R.mean(axis=0)  # N

        # Centered returns: r_{t,i} - μ_i
        Rc = R - mu

        # x = [w(0..N-1), y(0..T-1), z(0..T-1)]   length N + 2T
        n_var = N + 2 * T

        # ---- Objective: c = [0...0, 1...1, 1...1] ----
        c = np.concatenate([np.zeros(N), np.ones(T), np.ones(T)])

        # ---- Equality constraints ----
        # (1) Σ w_i = 1
        # (T) y_t - z_t = Σ_i Rc_{t,i} w_i  =>  Σ_i Rc_{t,i} w_i - y_t + z_t = 0
        A_eq = np.zeros((1 + T, n_var))
        b_eq = np.zeros(1 + T)

        # Sum-to-one
        if constraints.sum_to is not None:
            A_eq[0, :N] = 1.0
            b_eq[0] = constraints.sum_to
        else:
            # Drop the row if no sum constraint
            A_eq = A_eq[1:]
            b_eq = b_eq[1:]
            offset = 0
        offset = 1 if constraints.sum_to is not None else 0

        # MAD definition rows
        for t in range(T):
            row = offset + t
            A_eq[row, :N] = Rc[t]
            A_eq[row, N + t] = -1.0     # y_t coefficient (LHS - y + z = 0)
            A_eq[row, N + T + t] = 1.0  # z_t coefficient
            b_eq[row] = 0.0

        # ---- Inequality constraints ----
        A_ub_list = []
        b_ub_list = []

        # μ' w >= target_return  =>  -μ' w <= -target_return
        if constraints.target_return is not None:
            row = np.concatenate([-mu, np.zeros(2 * T)])
            A_ub_list.append(row)
            b_ub_list.append(-constraints.target_return)

        A_ub = np.array(A_ub_list) if A_ub_list else None
        b_ub = np.array(b_ub_list) if b_ub_list else None

        # ---- Bounds ----
        w_bounds = constraints.get_bounds(N)
        bounds = w_bounds + [(0.0, None)] * (2 * T)  # y_t, z_t >= 0

        # ---- Solve ----
        res = sco.linprog(
            c,
            A_ub=A_ub, b_ub=b_ub,
            A_eq=A_eq, b_eq=b_eq,
            bounds=bounds,
            method="highs",
            options={"disp": False, "presolve": True},
        )

        if not res.success:
            return OptimizationResult(
                weights=pd.Series(np.full(N, np.nan), index=returns.columns),
                expected_return=None,
                risk=float("nan"),
                risk_measure="mad",
                converged=False,
                diagnostics={"backend": "linprog_highs", "message": res.message},
                raw=res,
            )

        w_opt = res.x[:N]
        # MAD = (1/T) Σ (y_t + z_t) = (1/T) Σ |Rc_t w|
        mad_value = float(res.fun / T)
        port_ret = float(mu @ w_opt)

        return OptimizationResult(
            weights=pd.Series(w_opt, index=returns.columns),
            expected_return=port_ret,
            risk=mad_value,
            risk_measure="mad",
            converged=True,
            diagnostics={
                "backend": "linprog_highs",
                "n_variables": n_var,
                "n_equality": A_eq.shape[0],
                "n_inequality": 0 if A_ub is None else A_ub.shape[0],
            },
            raw=res,
        )
