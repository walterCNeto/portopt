"""Tracking Error optimization (Roll 1992, Jorion 2003)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import optimize

from portopt.estimators import Moments, LedoitWolfCC, SampleMean
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


class TrackingError(OptimizationModel):
    """Minimize tracking error vs a benchmark.

    Formulation (Jorion 2003):

        TE(omega) = sqrt((omega - omega_B)' Sigma (omega - omega_B))

    Two modes:
      1. target_te is None: pure TE minimization (long-only, sum=1)
      2. target_te is set: maximize excess return s.t. TE <= target_te

    The benchmark weights omega_B must be passed via
    constraints.benchmark_weights. Defaults to equal-weight if absent (with
    a warning).
    """

    name = "tracking_error"
    native_risk_measure = "tracking_error"
    requires_returns = True
    supports_short = False

    def __init__(
        self,
        target_te: float | None = None,
        cov_estimator=None,
        mean_estimator=None,
        backend: str = "scipy",
    ):
        self.target_te = target_te
        self.cov_estimator = cov_estimator or LedoitWolfCC()
        self.mean_estimator = mean_estimator or SampleMean()
        self.backend = backend

    def fit(self, log_returns, constraints=None):
        constraints = constraints or ConstraintSet()
        T, N = log_returns.shape
        names = list(log_returns.columns)

        moments = Moments.fit(log_returns, self.mean_estimator, self.cov_estimator)
        mu = moments.mean.flatten()
        Sigma = moments.cov

        if constraints.benchmark_weights is not None:
            omega_B = np.asarray(constraints.benchmark_weights, dtype=float)
            if len(omega_B) != N:
                raise ValueError(
                    f"benchmark_weights has {len(omega_B)} entries, "
                    f"expected {N} (one per asset)"
                )
        else:
            omega_B = np.ones(N) / N
            warnings.warn(
                "No benchmark_weights set; defaulting to equal-weight. "
                "Pass constraints.benchmark_weights for meaningful tracking.",
                stacklevel=2,
            )

        if self.target_te is None:
            return self._minimize_te(Sigma, mu, omega_B, constraints, names)
        else:
            return self._max_excess_return(Sigma, mu, omega_B, constraints, names)

    def _minimize_te(self, Sigma, mu, omega_B, constraints, names):
        N = len(omega_B)
        lb, ub = constraints.bounds
        sum_to = constraints.sum_to or 1.0

        def te_sq(omega):
            d = omega - omega_B
            return float(d @ Sigma @ d)

        def te_sq_grad(omega):
            return 2.0 * Sigma @ (omega - omega_B)

        cons = [{"type": "eq", "fun": lambda w: float(np.sum(w) - sum_to)}]
        if constraints.target_return is not None:
            cons.append({
                "type": "ineq",
                "fun": lambda w: float(w @ mu - constraints.target_return),
            })

        bounds = [(lb, ub)] * N
        x0 = omega_B.copy()

        res = optimize.minimize(
            te_sq, x0, jac=te_sq_grad, method="SLSQP",
            bounds=bounds, constraints=cons,
            options={"maxiter": 200, "ftol": 1e-10},
        )

        omega = np.clip(res.x, lb, ub)
        if omega.sum() > 0:
            omega = omega / omega.sum() * sum_to
        te_value = float(np.sqrt(max(te_sq(omega), 0.0)))

        return OptimizationResult(
            weights={n: float(w) for n, w in zip(names, omega)},
            expected_return=float(omega @ mu),
            risk=te_value,
            risk_measure="tracking_error",
            converged=bool(res.success),
            diagnostics={
                "backend": "scipy_slsqp",
                "iterations": int(res.nit),
                "message": str(res.message),
                "benchmark_weights": omega_B.tolist(),
                "mode": "minimize_te",
            },
        )

    def _max_excess_return(self, Sigma, mu, omega_B, constraints, names):
        N = len(omega_B)
        lb, ub = constraints.bounds
        sum_to = constraints.sum_to or 1.0
        te_sq_limit = self.target_te ** 2

        def neg_excess(omega):
            return -float((omega - omega_B) @ mu)

        def neg_excess_grad(omega):
            return -mu

        def te_budget(omega):
            d = omega - omega_B
            return te_sq_limit - float(d @ Sigma @ d)

        cons = [
            {"type": "eq", "fun": lambda w: float(np.sum(w) - sum_to)},
            {"type": "ineq", "fun": te_budget},
        ]
        bounds = [(lb, ub)] * N
        x0 = omega_B.copy()

        res = optimize.minimize(
            neg_excess, x0, jac=neg_excess_grad, method="SLSQP",
            bounds=bounds, constraints=cons,
            options={"maxiter": 200, "ftol": 1e-10},
        )

        omega = np.clip(res.x, lb, ub)
        if omega.sum() > 0:
            omega = omega / omega.sum() * sum_to
        d = omega - omega_B
        te_value = float(np.sqrt(max(d @ Sigma @ d, 0.0)))

        return OptimizationResult(
            weights={n: float(w) for n, w in zip(names, omega)},
            expected_return=float(omega @ mu),
            risk=te_value,
            risk_measure="tracking_error",
            converged=bool(res.success),
            diagnostics={
                "backend": "scipy_slsqp",
                "iterations": int(res.nit),
                "message": str(res.message),
                "benchmark_weights": omega_B.tolist(),
                "target_te": self.target_te,
                "mode": "max_excess_return",
            },
        )
