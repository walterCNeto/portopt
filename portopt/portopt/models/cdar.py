"""Conditional Drawdown-at-Risk (Chekhlov-Uryasev-Zabarankin 2003).

TODO: implement linearized formulation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from portopt.models.base import ConstraintSet, OptimizationModel, OptimizationResult


class CDaR(OptimizationModel):
    """Mean-CDaR portfolio optimizer. STUB."""

    name = "cdar"
    requires_returns = True
    supports_short = False
    native_risk_measure = "cdar"

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        raise NotImplementedError(
            "CDaR is a roadmap item. Use riskfolio-lib in the meantime: "
            "rp.Portfolio(returns).optimization(model='Classic', rm='CDaR', ...)"
        )
