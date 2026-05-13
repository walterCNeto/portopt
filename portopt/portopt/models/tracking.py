"""Tracking Error optimization (Chagas §3.3).

Solves: max  μ' (w - w_B)   (active return)
        s.t. (w - w_B)' Σ (w - w_B) <= TE_target²
             constraints

TODO: implement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from portopt.models.base import ConstraintSet, OptimizationModel, OptimizationResult


class TrackingError(OptimizationModel):
    """Mean-Tracking-Error portfolio optimizer. STUB."""

    name = "tracking_error"
    requires_returns = False
    supports_short = False
    native_risk_measure = "tracking_error"

    def __init__(self, target_te: float):
        self.target_te = target_te

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        if constraints.benchmark_weights is None:
            raise ValueError("TrackingError requires constraints.benchmark_weights")
        raise NotImplementedError("TrackingError model is a roadmap item.")
