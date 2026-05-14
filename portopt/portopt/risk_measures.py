"""Risk measures (classical literature, §3-§4 of standard textbooks).

Pure functions — they take weights + data and return scalars.
Used as objectives during optimization AND for reporting.

Implemented:
- Volatility (Markowitz)
- MAD (Konno-Yamazaki 1991)
- Downside Risk (Sortino-Meer 1991)
- VaR (parametric and historical)
- CVaR (Rockafellar-Uryasev 2000)
- CDaR (Chekhlov-Uryasev-Zabarankin 2003)
- Tracking Error
- Marginal Risk Contribution & Risk Contribution (Euler decomposition)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Volatility & Variance
# ---------------------------------------------------------------------------

def variance(weights: np.ndarray, cov: np.ndarray) -> float:
    """Portfolio variance: w' Σ w."""
    w = np.asarray(weights).flatten()
    return float(w @ cov @ w)


def volatility(weights: np.ndarray, cov: np.ndarray) -> float:
    """Portfolio volatility: sqrt(w' Σ w)."""
    return float(np.sqrt(max(variance(weights, cov), 0.0)))


# ---------------------------------------------------------------------------
# MAD
# ---------------------------------------------------------------------------

def mad(weights: np.ndarray, returns: pd.DataFrame | np.ndarray) -> float:
    """Mean-Absolute Deviation of portfolio returns.

    MAD = (1/(T-1)) Σ |r_{t,P} - μ_P|
    """
    R = np.asarray(returns)
    w = np.asarray(weights).flatten()
    port_rets = R @ w
    mu_p = port_rets.mean()
    return float(np.mean(np.abs(port_rets - mu_p)))


# ---------------------------------------------------------------------------
# Downside Risk
# ---------------------------------------------------------------------------

def downside_risk(
    weights: np.ndarray,
    returns: pd.DataFrame | np.ndarray,
    mar: float = 0.0,
) -> float:
    """Downside Risk = sqrt( mean( min(r - MAR, 0)² ) ).

    Parameters
    ----------
    mar : float
        Minimum Acceptable Return. Common values:
        - 0.0 in excess-return space
        - μ (mean) for semi-deviation
        - risk-free rate
    """
    R = np.asarray(returns)
    w = np.asarray(weights).flatten()
    port_rets = R @ w
    downside = np.minimum(port_rets - mar, 0.0)
    return float(np.sqrt(np.mean(downside ** 2)))


# ---------------------------------------------------------------------------
# VaR / CVaR
# ---------------------------------------------------------------------------

def var_historical(
    weights: np.ndarray,
    returns: pd.DataFrame | np.ndarray,
    alpha: float = 0.05,
) -> float:
    """Historical VaR at significance α (left tail, returned as a *loss* = -quantile).

    VaR_α = -F^{-1}(α) where F is the portfolio return CDF.
    """
    R = np.asarray(returns)
    w = np.asarray(weights).flatten()
    port_rets = R @ w
    return float(-np.quantile(port_rets, alpha))


def cvar_historical(
    weights: np.ndarray,
    returns: pd.DataFrame | np.ndarray,
    alpha: float = 0.05,
) -> float:
    """Historical CVaR / Expected Shortfall at significance α.

    CVaR_α = -E[ R | R <= F^{-1}(α) ]   (expressed as a positive loss).
    """
    R = np.asarray(returns)
    w = np.asarray(weights).flatten()
    port_rets = R @ w
    q = np.quantile(port_rets, alpha)
    tail = port_rets[port_rets <= q]
    if len(tail) == 0:
        return float(-q)
    return float(-tail.mean())


def cvar_rockafellar(
    weights: np.ndarray,
    scenarios: np.ndarray,
    var_value: float,
    alpha: float = 0.05,
) -> float:
    """Rockafellar-Uryasev CVaR auxiliary function .

    F_α(w, z) = z + (1/(Mα)) Σ max(0, -R_P(w, r_m) - z)

    where z is the candidate VaR and `scenarios` is the M × N matrix of return scenarios.

    Used inside CVaR optimization where w *and* z are jointly optimized.
    """
    w = np.asarray(weights).flatten()
    port_rets = scenarios @ w
    M = len(port_rets)
    excess = np.maximum(0.0, -port_rets - var_value)
    return float(var_value + excess.sum() / (M * alpha))


# ---------------------------------------------------------------------------
# CDaR (Conditional Drawdown-at-Risk)
# ---------------------------------------------------------------------------

def drawdown_series(weights: np.ndarray, returns: pd.DataFrame | np.ndarray) -> np.ndarray:
    """Time series of portfolio drawdowns (uncompounded).

    Δ_τ = max_{k≤τ} Σ r_i,s w_i over s∈[1,k] - Σ r_i,s w_i over s∈[1,τ]
    """
    R = np.asarray(returns)
    w = np.asarray(weights).flatten()
    cumlog = np.cumsum(R @ w)
    running_max = np.maximum.accumulate(cumlog)
    return running_max - cumlog


def cdar_historical(
    weights: np.ndarray,
    returns: pd.DataFrame | np.ndarray,
    alpha: float = 0.05,
) -> float:
    """Historical CDaR: average of the α worst drawdowns."""
    dd = drawdown_series(weights, returns)
    threshold = np.quantile(dd, 1 - alpha)
    worst = dd[dd >= threshold]
    if len(worst) == 0:
        return float(threshold)
    return float(worst.mean())


def max_drawdown(weights: np.ndarray, returns: pd.DataFrame | np.ndarray) -> float:
    """Maximum drawdown (the worst peak-to-trough decline)."""
    return float(drawdown_series(weights, returns).max())


# ---------------------------------------------------------------------------
# Tracking Error
# ---------------------------------------------------------------------------

def tracking_error(
    weights: np.ndarray,
    benchmark_weights: np.ndarray,
    cov: np.ndarray,
) -> float:
    """Ex-ante Tracking Error: sqrt((w_P - w_B)' Σ (w_P - w_B)).

    """
    diff = np.asarray(weights).flatten() - np.asarray(benchmark_weights).flatten()
    return float(np.sqrt(max(diff @ cov @ diff, 0.0)))


# ---------------------------------------------------------------------------
# Risk Contributions (Euler decomposition)
# ---------------------------------------------------------------------------

def marginal_risk_contrib(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Marginal Risk Contribution: MRC_i = (Σ w)_i / sqrt(w'Σw).

    """
    w = np.asarray(weights).flatten()
    vol = volatility(w, cov)
    if vol == 0:
        return np.zeros_like(w)
    return (cov @ w) / vol


def risk_contrib(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Risk Contribution: RC_i = w_i × MRC_i.

    Property: Σ_i RC_i = vol_P (Euler's theorem).
    """
    w = np.asarray(weights).flatten()
    return w * marginal_risk_contrib(w, cov)


def risk_contrib_pct(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Percentual Risk Contribution: RC_i / vol_P. Sums to 1."""
    rc = risk_contrib(weights, cov)
    total = rc.sum()
    if total == 0:
        return np.zeros_like(rc)
    return rc / total


# ---------------------------------------------------------------------------
# Risk measure registry (for the menu/UI)
# ---------------------------------------------------------------------------

RISK_MEASURES = {
    "vol": volatility,
    "variance": variance,
    "mad": mad,
    "downside_risk": downside_risk,
    "var": var_historical,
    "cvar": cvar_historical,
    "cdar": cdar_historical,
    "max_drawdown": max_drawdown,
}


def evaluate(
    name: str,
    weights: np.ndarray,
    returns: Optional[pd.DataFrame] = None,
    cov: Optional[np.ndarray] = None,
    **kwargs,
) -> float:
    """Convenience: evaluate a risk measure by name.

    Dispatches arguments based on what the measure needs.
    """
    fn = RISK_MEASURES[name]
    if name in ("vol", "variance"):
        if cov is None:
            raise ValueError(f"{name!r} requires cov")
        return fn(weights, cov, **kwargs)
    if returns is None:
        raise ValueError(f"{name!r} requires returns")
    return fn(weights, returns, **kwargs)
