"""Tier 0 — Naïve allocation models.

These need no optimization. They serve as baselines for backtesting
and as smoke tests for the engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from portopt.estimators import EWMACov, SampleCov
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


class EqualWeight(OptimizationModel):
    """Equal-weight portfolio (1/N).

    DeMiguel-Garlappi-Uppal (2009) show this is hard to beat out-of-sample.
    """

    name = "equal_weight"
    requires_returns = False
    supports_short = False
    native_risk_measure = "vol"

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        N = returns.shape[1]
        w = pd.Series(np.full(N, 1.0 / N), index=returns.columns)
        cov = returns.cov().values
        return OptimizationResult(
            weights=w,
            expected_return=float(w.values @ returns.mean().values),
            risk=float(np.sqrt(w.values @ cov @ w.values)),
            risk_measure="vol",
            converged=True,
        )


class BuyAndHold(OptimizationModel):
    """Buy-and-Hold: equal-weight at inception, no rebalancing.

    The model produces equal weights here; the backtest engine knows to
    skip rebalancing for this model. Useful as a long-term passive baseline.
    """

    name = "buy_and_hold"
    requires_returns = False
    supports_short = False
    native_risk_measure = "vol"

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        # Same starting weights as EW; engine will not rebalance
        return EqualWeight().fit(returns, constraints, **kwargs)


class InverseVolatility(OptimizationModel):
    """Inverse Volatility: w_i ∝ 1/σ_i (Chagas §4.2).

    Ignores correlations entirely; allocates more to less volatile assets.
    """

    name = "inverse_vol"
    requires_returns = False
    supports_short = False
    native_risk_measure = "vol"

    def __init__(self, vol_estimator: str = "sample", ewma_halflife: int = 63):
        """
        Parameters
        ----------
        vol_estimator : "sample" or "ewma"
            Chagas recommends EWMA in §4.2 (smoothing helps recency).
        """
        self.vol_estimator = vol_estimator
        self.ewma_halflife = ewma_halflife

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        if self.vol_estimator == "ewma":
            vols = returns.ewm(halflife=self.ewma_halflife, adjust=True).std().iloc[-1].values
        else:
            vols = returns.std().values

        # Guard against zero vols (e.g. cash row)
        inv = np.where(vols > 0, 1.0 / np.maximum(vols, 1e-12), 0.0)
        w = inv / inv.sum() if inv.sum() > 0 else np.ones(len(vols)) / len(vols)
        w_series = pd.Series(w, index=returns.columns)

        cov = returns.cov().values
        return OptimizationResult(
            weights=w_series,
            expected_return=float(w @ returns.mean().values),
            risk=float(np.sqrt(max(w @ cov @ w, 0.0))),
            risk_measure="vol",
            converged=True,
            diagnostics={"vol_estimator": self.vol_estimator},
        )
