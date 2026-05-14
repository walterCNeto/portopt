"""Risk Budgeting per group .

Generalizes ERC: instead of equal risk contribution per asset, target a
specific risk budget per asset group (e.g. 20% Metals, 30% Energy, ...).

Two formulations:
- Approach 1: hard constraint per group, ERC objective within group.
- Approach 2: soft objective summing squared deviations from group budgets.

Both approaches are valid but yield different per-asset distributions.
"""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np
import pandas as pd
import scipy.optimize as sco

from portopt.estimators import SampleCov, CovEstimator
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)
from portopt.models.naive import InverseVolatility


class RiskBudget(OptimizationModel):
    """Risk Budgeting portfolio with per-group risk allocation targets.

    Parameters
    ----------
    approach : "1" or "2"
        Formulation selector (two valid approaches from the literature).
    cov_estimator : CovEstimator, optional
    warm_start : "iv" or "equal"
        Warm start for SLSQP (IV recommended as warm-start per the literature).

    The actual group targets and group->assets mapping come from the
    `ConstraintSet`:
        constraints.asset_groups = {"Metals": ["Gold", ...], "Energy": [...]}
        constraints.group_risk_budgets = {"Metals": 0.20, "Energy": 0.30, ...}
    """

    name = "risk_budget"
    requires_returns = False
    supports_short = False
    native_risk_measure = "vol"

    def __init__(
        self,
        approach: Literal["1", "2"] = "1",
        cov_estimator: Optional[CovEstimator] = None,
        warm_start: str = "iv",
        tol: float = 1e-12,
        maxiter: int = 10000,
    ):
        if approach not in ("1", "2"):
            raise ValueError("approach must be '1' or '2'")
        self.approach = approach
        self.cov_estimator = cov_estimator or SampleCov()
        self.warm_start = warm_start
        self.tol = tol
        self.maxiter = maxiter

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        if not constraints.asset_groups or not constraints.group_risk_budgets:
            raise ValueError(
                "RiskBudget requires constraints.asset_groups and "
                "constraints.group_risk_budgets to be set"
            )

        cov = self.cov_estimator.fit(returns)
        N = cov.shape[0]
        asset_names = list(returns.columns)

        # Map groups to index arrays
        groups = list(constraints.group_risk_budgets.keys())
        group_idx = {}
        for g in groups:
            names_in_g = constraints.asset_groups.get(g, [])
            idx = [asset_names.index(a) for a in names_in_g if a in asset_names]
            if not idx:
                raise ValueError(f"Group {g!r} has no assets in the universe")
            group_idx[g] = np.array(idx)

        budgets = np.array([constraints.group_risk_budgets[g] for g in groups])
        if not np.isclose(budgets.sum(), 1.0):
            raise ValueError(f"Group budgets must sum to 1, got {budgets.sum():.4f}")

        # Warm start
        if self.warm_start == "iv":
            w0 = InverseVolatility().fit(returns, constraints).weights.values
        else:
            w0 = np.ones(N) / N

        target_var = (constraints.target_vol ** 2) if constraints.target_vol else None

        # Build objective per approach
        if self.approach == "1":
            # Approach 1: ERC within (varp denominator) + hard group constraints
            def objective(w):
                Ew = cov @ w
                varp = float(w @ cov @ w)
                if varp <= 0:
                    return 1e6
                return float(np.sum((w * Ew / varp - 1.0 / N) ** 2))

            cons = []
            if constraints.sum_to is not None:
                cons.append({"type": "eq", "fun": lambda w: float(np.sum(w) - constraints.sum_to)})
            if target_var is not None:
                cons.append({"type": "eq", "fun": lambda w: float(w @ cov @ w - target_var)})

            # Hard group constraints: Σ_{i∈G} w_i * (Σw)_i / (w'Σw) = RB_G
            for k, g in enumerate(groups):
                idx = group_idx[g]
                budget = budgets[k]
                def make_con(idx=idx, budget=budget):
                    def fn(w):
                        Ew = cov @ w
                        varp = float(w @ cov @ w)
                        if varp <= 0:
                            return -budget
                        grp_contrib = float(np.sum(w[idx] * Ew[idx]) / varp)
                        return grp_contrib - budget
                    return fn
                cons.append({"type": "eq", "fun": make_con()})

        else:
            # Approach 2: soft objective, just sum-to-one
            def objective(w):
                Ew = cov @ w
                varp = float(w @ cov @ w)
                if varp <= 0:
                    return 1e6
                res = 0.0
                for k, g in enumerate(groups):
                    idx = group_idx[g]
                    group_contrib = float(np.sum(w[idx] * Ew[idx]) / varp)
                    res += (group_contrib - budgets[k]) ** 2
                return res

            cons = []
            if constraints.sum_to is not None:
                cons.append({"type": "eq", "fun": lambda w: float(np.sum(w) - constraints.sum_to)})
            if target_var is not None:
                cons.append({"type": "eq", "fun": lambda w: float(w @ cov @ w - target_var)})

        bounds = constraints.get_bounds(N)

        res = sco.minimize(
            objective, w0, method="SLSQP", bounds=bounds, constraints=cons,
            tol=self.tol, options={"maxiter": self.maxiter},
        )

        w_opt = res.x
        vol = float(np.sqrt(max(w_opt @ cov @ w_opt, 0.0)))
        port_ret = float(returns.mean().values @ w_opt)

        # Report realized group contributions
        Ew = cov @ w_opt
        realized = {}
        if vol > 0:
            varp = vol ** 2
            for g in groups:
                idx = group_idx[g]
                realized[g] = float(np.sum(w_opt[idx] * Ew[idx]) / varp)

        return OptimizationResult(
            weights=pd.Series(w_opt, index=returns.columns),
            expected_return=port_ret,
            risk=vol,
            risk_measure="vol",
            converged=bool(res.success),
            diagnostics={
                "backend": "scipy_slsqp",
                "approach": self.approach,
                "warm_start": self.warm_start,
                "group_budgets_target": {g: float(b) for g, b in zip(groups, budgets)},
                "group_budgets_realized": realized,
                "message": str(res.message),
            },
            raw=res,
        )
