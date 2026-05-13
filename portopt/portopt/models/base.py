"""Base abstractions for optimization models.

All models implement the same Protocol: receive returns (or moments) +
constraints → return weights + diagnostics. This makes them interchangeable
inside the BacktestEngine and the API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constraint specification
# ---------------------------------------------------------------------------

@dataclass
class ConstraintSet:
    """Container for portfolio constraints used by optimizers.

    Attributes
    ----------
    bounds : (float, float) or list of (float, float)
        Lower and upper bounds per weight. If single tuple, applied to all assets.
        Use (0.0, 1.0) for long-only, (-1.0, 1.0) to allow shorts.
    sum_to : float, default 1.0
        Constraint Σ w_i = sum_to. Set to None to disable.
    target_return : float, optional
        Minimum target portfolio expected return (inequality: R_P >= target).
    target_vol : float, optional
        Maximum target portfolio volatility (inequality: vol_P <= target).
    target_risk : float, optional
        Maximum target value for the model's native risk measure
        (e.g. MAD for MAD model, CVaR for CVaR model).
    risk_aversion : float, optional
        Used by utility-based models (max U = R - 0.5 λ vol²).
    group_bounds : dict
        Allocation bounds per asset group. {"Energy": (0.10, 0.30), ...}
    group_risk_budgets : dict
        Risk budget targets per group (for Risk Budgeting model).
    asset_groups : dict
        Map group_name -> list of asset names.
    benchmark_weights : np.ndarray, optional
        Used by Tracking Error model.
    """

    bounds: tuple[float, float] | list[tuple[float, float]] = (0.0, 1.0)
    sum_to: Optional[float] = 1.0
    target_return: Optional[float] = None
    target_vol: Optional[float] = None
    target_risk: Optional[float] = None
    risk_aversion: Optional[float] = None
    group_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    group_risk_budgets: dict[str, float] = field(default_factory=dict)
    asset_groups: dict[str, list[str]] = field(default_factory=dict)
    benchmark_weights: Optional[np.ndarray] = None

    def get_bounds(self, n: int) -> list[tuple[float, float]]:
        """Return per-asset bounds as a list of N tuples."""
        if isinstance(self.bounds, tuple):
            return [self.bounds] * n
        if len(self.bounds) != n:
            raise ValueError(f"bounds has {len(self.bounds)} entries but N={n}")
        return list(self.bounds)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class OptimizationResult:
    """Standard return value of any OptimizationModel.fit() call.

    Attributes
    ----------
    weights : pd.Series
        Optimal weights, indexed by asset name.
    expected_return : float, optional
        Portfolio expected return at the optimal weights, if computable.
    risk : float
        Portfolio risk at the optimal weights, in the model's native unit.
    risk_measure : str
        Name of the native risk measure ("vol", "mad", "cvar", "cdar", "tracking_error", ...).
    converged : bool
        Whether the solver reported convergence.
    diagnostics : dict
        Solver-specific diagnostics (iterations, status, condition number, etc.).
    raw : object
        Raw object returned by the underlying solver (for debugging).
    """

    weights: pd.Series
    expected_return: Optional[float] = None
    risk: float = float("nan")
    risk_measure: str = "vol"
    converged: bool = True
    diagnostics: dict = field(default_factory=dict)
    raw: Any = None

    def __repr__(self) -> str:
        top_w = self.weights.sort_values(ascending=False).head(5)
        top_str = ", ".join(f"{k}={v:.3f}" for k, v in top_w.items())
        ret_str = f"E[R]={self.expected_return:.4f}" if self.expected_return is not None else "E[R]=n/a"
        return (
            f"OptimizationResult({self.risk_measure}={self.risk:.4f}, {ret_str}, "
            f"converged={self.converged}, top_5={{{top_str}}})"
        )


# ---------------------------------------------------------------------------
# Abstract model
# ---------------------------------------------------------------------------

class OptimizationModel(ABC):
    """Abstract base class for all portfolio optimization models.

    Implementations must declare:
    - name : short identifier used in the menu / CLI / API
    - requires_returns : True if model needs full return history,
      False if it only needs estimated moments (μ, Σ)
    - supports_short : whether negative weights are allowed
    - native_risk_measure : name of the model's risk metric
    """

    name: str = "abstract"
    requires_returns: bool = False  # True for MAD/CVaR/CDaR, False for MV/HRP/etc
    supports_short: bool = True
    native_risk_measure: str = "vol"

    @abstractmethod
    def fit(
        self,
        returns: pd.DataFrame,
        constraints: ConstraintSet,
        **kwargs,
    ) -> OptimizationResult:
        """Run optimization and return optimal weights + diagnostics."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} (name={self.name!r})>"


# ---------------------------------------------------------------------------
# Backend selector
# ---------------------------------------------------------------------------

class Backend:
    """Solver backend selector.

    SCIPY = scipy.optimize (educational, mirrors Chagas' notebooks)
    LINPROG = scipy.optimize.linprog with HiGHS (linearized problems)
    CVXPY = cvxpy (production-grade convex)
    """

    SCIPY = "scipy"
    LINPROG = "linprog"
    CVXPY = "cvxpy"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.SCIPY, cls.LINPROG, cls.CVXPY]


# ---------------------------------------------------------------------------
# Helpers for building scipy constraint dicts (used by most SciPy-based models)
# ---------------------------------------------------------------------------

def build_scipy_constraints(
    constraints: ConstraintSet,
    mu: Optional[np.ndarray] = None,
    cov: Optional[np.ndarray] = None,
    asset_names: Optional[list[str]] = None,
) -> list[dict]:
    """Convert ConstraintSet to list of scipy.optimize constraint dicts.

    Note: bounds are handled separately via the `bounds` parameter of minimize().
    """
    cons = []
    n = len(mu) if mu is not None else (len(cov) if cov is not None else None)

    # Σ w = sum_to
    if constraints.sum_to is not None:
        s = constraints.sum_to
        cons.append({"type": "eq", "fun": lambda w, s=s: float(np.sum(w) - s)})

    # R_P >= target_return
    if constraints.target_return is not None and mu is not None:
        t = constraints.target_return
        mu_ = mu.flatten()
        cons.append({"type": "ineq", "fun": lambda w, mu_=mu_, t=t: float(mu_ @ w - t)})

    # vol_P <= target_vol  (i.e. tgt_vol² - w'Σw >= 0)
    if constraints.target_vol is not None and cov is not None:
        tv2 = float(constraints.target_vol) ** 2
        cons.append({"type": "ineq", "fun": lambda w, cov=cov, tv2=tv2: float(tv2 - w @ cov @ w)})

    # Group bounds (lower and upper per group)
    if constraints.group_bounds and asset_names is not None:
        for grp, (lb, ub) in constraints.group_bounds.items():
            idx = [asset_names.index(a) for a in constraints.asset_groups.get(grp, []) if a in asset_names]
            if not idx:
                continue
            cons.append({"type": "ineq", "fun": lambda w, idx=idx, lb=lb: float(np.sum(w[idx]) - lb)})
            cons.append({"type": "ineq", "fun": lambda w, idx=idx, ub=ub: float(ub - np.sum(w[idx]))})

    return cons


def initial_weights(n: int, kind: str = "equal") -> np.ndarray:
    """Standard initial weights for solvers."""
    if kind == "equal":
        return np.ones(n) / n
    if kind == "zero":
        return np.zeros(n)
    raise ValueError(f"Unknown initial_weights kind: {kind!r}")
