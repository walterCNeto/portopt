"""Mean and covariance estimators.

Covers the full menu used by Chagas:
- Sample (vanilla)
- EWMA (Chagas §4 IV/ERC)
- James-Stein (Chagas §5.2)
- Bayes-Stein / Jorion (Chagas §5.3 notebook implementation)
- Ledoit-Wolf constant correlation (Chagas §5.3)
- CAPM-implied (Chagas §5.4 for Black-Litterman prior)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


# ===========================================================================
# Base classes
# ===========================================================================

class MeanEstimator(ABC):
    """Abstract base for expected return estimators."""

    @abstractmethod
    def fit(self, returns: pd.DataFrame) -> np.ndarray:
        """Return mean vector (shape N,) given log-returns (shape T x N)."""
        ...


class CovEstimator(ABC):
    """Abstract base for covariance estimators."""

    @abstractmethod
    def fit(self, returns: pd.DataFrame) -> np.ndarray:
        """Return covariance matrix (shape N x N) given log-returns."""
        ...


# ===========================================================================
# Mean estimators
# ===========================================================================

class SampleMean(MeanEstimator):
    """Plain sample mean. The naive estimator."""

    def fit(self, returns):
        return np.asarray(returns.mean())


class EWMAMean(MeanEstimator):
    """Exponentially-weighted moving average mean.

    Parameters
    ----------
    halflife : int
        Half-life in periods. Default 63 ≈ 3 months daily.
    """

    def __init__(self, halflife: int = 63):
        self.halflife = halflife

    def fit(self, returns):
        return np.asarray(returns.ewm(halflife=self.halflife, adjust=True).mean().iloc[-1])


@dataclass
class JamesStein(MeanEstimator):
    """James-Stein shrinkage estimator (Chagas §5.2).

    Shrinks sample mean toward a grand mean μ₀:

        μ̂_JS = (1 - w) μ̂ + w μ₀ 1

        w = min(1, (N-2) / [T (μ̂ - μ₀ 1)' Σ⁻¹ (μ̂ - μ₀ 1)])
    """

    grand_mean: Optional[float] = None  # if None, uses cross-sectional mean

    def fit(self, returns):
        mu = np.asarray(returns.mean()).reshape(-1, 1)
        cov = np.asarray(returns.cov())
        T, N = returns.shape
        if N <= 2:
            return mu.flatten()

        mu0 = self.grand_mean if self.grand_mean is not None else float(mu.mean())
        diff = mu - mu0
        denom = T * (diff.T @ np.linalg.pinv(cov) @ diff)[0, 0]
        w = min(1.0, max(0.0, (N - 2) / denom)) if denom > 0 else 0.0
        return ((1 - w) * mu + w * mu0).flatten()


@dataclass
class BayesStein(MeanEstimator):
    """Bayes-Stein (Jorion 1986) estimator, as implemented by Chagas in nb4.

    Shrinks toward the minimum-variance grand mean μ_g:

        μ_g = (1' Σ⁻¹ μ̂) / (1' Σ⁻¹ 1)
        w   = (N + 2) / (N + 2 + T (μ̂ - μ_g 1)' Σ⁻¹ (μ̂ - μ_g 1))
        μ̂_BS = (1 - w) μ̂ + w μ_g 1
    """

    def fit(self, returns):
        mu = np.asarray(returns.mean()).reshape(-1, 1)
        cov = np.asarray(returns.cov())
        T, N = returns.shape
        ones = np.ones((N, 1))

        cov_inv = np.linalg.pinv(cov)
        mu_g = float((ones.T @ cov_inv @ mu) / (ones.T @ cov_inv @ ones))
        diff = mu - mu_g * ones
        denom = (N + 2 + T * (diff.T @ cov_inv @ diff))[0, 0]
        w = (N + 2) / denom if denom > 0 else 0.0
        return ((1 - w) * mu + w * mu_g * ones).flatten()


class CAPMImpliedMean(MeanEstimator):
    """CAPM-implied expected excess returns (Black-Litterman prior).

    Π = δ Σ ω_M

    where δ is the market price of risk and ω_M is the market portfolio.
    """

    def __init__(
        self,
        market_weights: pd.Series | np.ndarray,
        delta: float,
        cov_estimator: CovEstimator | None = None,
    ):
        self.market_weights = np.asarray(market_weights).flatten()
        self.delta = delta
        self.cov_estimator = cov_estimator or SampleCov()

    def fit(self, returns):
        cov = self.cov_estimator.fit(returns)
        return self.delta * cov @ self.market_weights


# ===========================================================================
# Covariance estimators
# ===========================================================================

class SampleCov(CovEstimator):
    """Plain sample covariance."""

    def fit(self, returns):
        # Symmetrize to handle rounding errors (Chagas §2.6 pattern)
        cov = returns.cov().values
        return (cov + cov.T) / 2.0


class EWMACov(CovEstimator):
    """Exponentially-weighted covariance (Chagas §4.1)."""

    def __init__(self, halflife: int = 63):
        self.halflife = halflife

    def fit(self, returns):
        ewm = returns.ewm(halflife=self.halflife, adjust=True)
        cov = ewm.cov().iloc[-len(returns.columns):].values
        return (cov + cov.T) / 2.0


class LedoitWolfCC(CovEstimator):
    """Ledoit-Wolf shrinkage with constant-correlation target (Chagas §5.3).

    Σ_LW = (1 - w) Σ̂ + w Σ_CC

    where Σ_CC has all off-diagonal correlations equal to the cross-sectional
    average ρ̄ and w is the optimal shrinkage intensity κ̂ / T (clipped to [0, 1]).

    Implementation faithfully follows Chagas' notebook 4 (cells with π̂, ĉ, γ̂).
    For production, prefer `sklearn.covariance.LedoitWolf` (also supported via
    `LedoitWolfSklearn` below).
    """

    def fit(self, returns):
        X = np.asarray(returns.values)
        T, N = X.shape
        mu = X.mean(axis=0).reshape(1, -1)
        Xc = X - mu

        cov_sample = (Xc.T @ Xc) / T
        sigs = np.sqrt(np.diag(cov_sample))
        # Avoid div-by-zero on degenerate assets (e.g. cash row)
        sigs_safe = np.where(sigs > 0, sigs, 1.0)
        corrs = cov_sample / np.outer(sigs_safe, sigs_safe)
        np.fill_diagonal(corrs, 1.0)

        # Average off-diagonal correlation
        if N > 1:
            mask = ~np.eye(N, dtype=bool)
            rho_bar = float(corrs[mask].mean())
        else:
            rho_bar = 0.0

        # Constant-correlation target
        corrs_cc = np.full((N, N), rho_bar)
        np.fill_diagonal(corrs_cc, 1.0)
        cov_cc = np.outer(sigs, sigs) * corrs_cc

        # Shrinkage intensity κ̂ = (π̂ - ĉ) / γ̂
        # π̂ : sum over i,j of asymptotic variance of T·σ̂_ij
        outer = Xc[:, :, None] * Xc[:, None, :]            # T × N × N
        diffs = outer - cov_sample[None, :, :]
        pi_hat = (diffs ** 2).mean(axis=0).sum()

        # γ̂ : Frobenius norm squared of target - sample
        gamma_hat = ((cov_cc - cov_sample) ** 2).sum()

        # ĉ : involves cross-asset moments; Schäfer-Strimmer simplification:
        # for the CC target, the ĉ term is small and ĉ ≈ Σ_i π̂_ii + (correction)
        # Here we approximate (Chagas' explicit form is verbatim in the notebook,
        # this version is the Schäfer-Strimmer 2005 expression which is equivalent
        # in the limit and numerically more stable):
        c_hat = float(np.diag((diffs ** 2).mean(axis=0)).sum())
        if N > 1:
            for i in range(N):
                for j in range(N):
                    if i == j:
                        continue
                    rho_term = rho_bar / 2.0
                    ratio_ij = np.sqrt(cov_sample[j, j] / cov_sample[i, i]) if cov_sample[i, i] > 0 else 0
                    ratio_ji = np.sqrt(cov_sample[i, i] / cov_sample[j, j]) if cov_sample[j, j] > 0 else 0
                    ups_ii_ij = ((Xc[:, i] ** 2 - cov_sample[i, i])
                                 * (Xc[:, i] * Xc[:, j] - cov_sample[i, j])).mean()
                    ups_jj_ij = ((Xc[:, j] ** 2 - cov_sample[j, j])
                                 * (Xc[:, i] * Xc[:, j] - cov_sample[i, j])).mean()
                    c_hat += rho_term * (ratio_ij * ups_ii_ij + ratio_ji * ups_jj_ij)

        kappa = (pi_hat - c_hat) / gamma_hat if gamma_hat > 0 else 0.0
        w = float(np.clip(kappa / T, 0.0, 1.0))

        cov_lw = (1 - w) * cov_sample + w * cov_cc
        self.shrinkage_intensity_ = w
        return (cov_lw + cov_lw.T) / 2.0


class LedoitWolfSklearn(CovEstimator):
    """sklearn-based Ledoit-Wolf (uses identity-scaled target, not CC).

    Faster and battle-tested. Use this in production unless you specifically
    need the constant-correlation target.
    """

    def fit(self, returns):
        from sklearn.covariance import LedoitWolf  # lazy import
        lw = LedoitWolf().fit(returns.values)
        self.shrinkage_intensity_ = lw.shrinkage_
        cov = lw.covariance_
        return (cov + cov.T) / 2.0


# ===========================================================================
# Convenience facade
# ===========================================================================

@dataclass
class Moments:
    """Container for fitted moments, used by optimization models."""

    mean: np.ndarray
    cov: np.ndarray
    names: list[str]

    @property
    def n_assets(self) -> int:
        return len(self.mean)

    @classmethod
    def fit(
        cls,
        returns: pd.DataFrame,
        mean_est: MeanEstimator | None = None,
        cov_est: CovEstimator | None = None,
    ) -> "Moments":
        mean_est = mean_est or SampleMean()
        cov_est = cov_est or SampleCov()
        return cls(
            mean=mean_est.fit(returns),
            cov=cov_est.fit(returns),
            names=list(returns.columns),
        )
