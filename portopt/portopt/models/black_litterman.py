"""Black-Litterman model (Black-Litterman 1992).

Implements the Bayesian derivation:
    μ_BL = [(τΣ)^-1 + P' Ω^-1 P]^-1 [(τΣ)^-1 Π + P' Ω^-1 Q]
    Σ_BL = [(τΣ)^-1 + P' Ω^-1 P]^-1

Optional Woodbury identity for numerical comparison.
After estimating μ_BL and Σ_BL, the final portfolio is obtained by running
a Mean-Variance optimization with the BL posteriors.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from portopt.estimators import SampleCov, CovEstimator
from portopt.models.base import (
    Backend,
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)
from portopt.models.markowitz import Markowitz


class BlackLitterman(OptimizationModel):
    """Black-Litterman portfolio optimization.

    Two-step:
    1. Combine equilibrium prior (Π = δ Σ ω_M) with investor views (P, Q, Ω)
       via Bayesian update to get posterior (μ_BL, Σ_BL).
    2. Run mean-variance optimization with the posterior.

    Parameters
    ----------
    market_weights : pd.Series or np.ndarray
        Market portfolio weights ω_M (e.g. ACWI weights for global equities).
        Should align with the asset columns in `returns`.
    delta : float
        Market price of risk (risk aversion coefficient). Typically
        δ = (E[R_M] - R_F) / σ_M².
    P : np.ndarray
        Views matrix, K × N. Each row picks linear combinations of assets.
    Q : np.ndarray
        Views vector, K × 1. Expected (excess) returns of the K linear combinations.
    omega : np.ndarray, optional
        Views covariance, K × K. If None, uses He-Litterman default: diag(P τΣ P').
    tau : float
        Confidence in the prior, 0 < τ < 1.
        - Small τ: high confidence in equilibrium, views have small impact.
        - Large τ: low confidence in equilibrium, views dominate.
    cov_estimator : CovEstimator, optional
        Default: SampleCov.
    """

    name = "black_litterman"
    requires_returns = False
    supports_short = True
    native_risk_measure = "vol"

    def __init__(
        self,
        market_weights: pd.Series | np.ndarray,
        delta: float,
        P: np.ndarray,
        Q: np.ndarray,
        omega: Optional[np.ndarray] = None,
        tau: float = 0.05,
        cov_estimator: Optional[CovEstimator] = None,
        backend: str = Backend.SCIPY,
    ):
        self.market_weights = np.asarray(market_weights).flatten()
        self.delta = float(delta)
        self.P = np.asarray(P)
        self.Q = np.asarray(Q).reshape(-1, 1)
        self.omega = omega
        self.tau = float(tau)
        self.cov_estimator = cov_estimator or SampleCov()
        self.backend = backend

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        N = returns.shape[1]
        if len(self.market_weights) != N:
            raise ValueError(
                f"market_weights has {len(self.market_weights)} entries but N={N}"
            )

        cov = self.cov_estimator.fit(returns)

        # Equilibrium implied excess returns
        Pi = self.delta * cov @ self.market_weights.reshape(-1, 1)  # N × 1

        # Default omega (He-Litterman): diagonal of P τΣ P'
        tau_sigma = self.tau * cov
        if self.omega is None:
            omega = np.diag(np.diag(self.P @ tau_sigma @ self.P.T))
        else:
            omega = np.asarray(self.omega)

        # Posterior moments — direct form (numerically more sensitive)
        tau_sigma_inv = np.linalg.pinv(tau_sigma)
        omega_inv = np.linalg.pinv(omega)
        post_cov = np.linalg.pinv(tau_sigma_inv + self.P.T @ omega_inv @ self.P)
        mu_bl = post_cov @ (tau_sigma_inv @ Pi + self.P.T @ omega_inv @ self.Q)

        # Woodbury form (for cross-check)
        mu_bl_w = Pi + tau_sigma @ self.P.T @ np.linalg.pinv(
            self.P @ tau_sigma @ self.P.T + omega
        ) @ (self.Q - self.P @ Pi)

        # Numerical sanity check
        woodbury_diff = float(np.max(np.abs(mu_bl - mu_bl_w)))

        # Now run MV optimization with the posterior (μ_BL, Σ_BL)
        # We construct a "synthetic" returns DataFrame by combining BL mean with a
        # MVN sample of the BL covariance. But Markowitz only needs μ, Σ — so we
        # bypass the estimator step and inject the BL moments directly.

        # Override estimators via a custom class
        class _BLMeanEstimator:
            def fit(_, _returns):
                return mu_bl.flatten()

        class _BLCovEstimator:
            def fit(_, _returns):
                # Posterior total covariance is Σ + Σ_BL (predictive distribution)
                return cov + post_cov

        mv = Markowitz(
            backend=self.backend,
            mean_estimator=_BLMeanEstimator(),
            cov_estimator=_BLCovEstimator(),
        )
        result = mv.fit(returns, constraints)

        # Augment diagnostics with BL-specific info
        result.diagnostics["bl_pi"] = Pi.flatten().tolist()
        result.diagnostics["bl_mu"] = mu_bl.flatten().tolist()
        result.diagnostics["bl_tau"] = self.tau
        result.diagnostics["bl_delta"] = self.delta
        result.diagnostics["woodbury_max_diff"] = woodbury_diff
        return result
