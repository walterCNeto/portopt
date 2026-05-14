"""Return computations and conversions.

All functions here are pure: they take prices/returns and return
new arrays/DataFrames without side effects. This makes them composable
with the backtest engine and the optimization models.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Log <-> Simple
# ---------------------------------------------------------------------------

def to_log_returns(prices: pd.DataFrame, dropna: bool = True) -> pd.DataFrame:
    """Convert price series to log returns: r_t = ln(P_t / P_{t-1}).

    Equivalent to `np.log1p(prices.pct_change())` (standard pattern).
    """
    log_rets = np.log1p(prices.pct_change())
    return log_rets.dropna() if dropna else log_rets


def to_simple_returns(prices: pd.DataFrame, dropna: bool = True) -> pd.DataFrame:
    """Convert price series to simple returns: R_t = P_t / P_{t-1} - 1."""
    rets = prices.pct_change()
    return rets.dropna() if dropna else rets


def log_to_simple(log_rets: pd.DataFrame | np.ndarray) -> pd.DataFrame | np.ndarray:
    """Convert log returns to simple returns: R = exp(r) - 1."""
    return np.expm1(log_rets)


def simple_to_log(simple_rets: pd.DataFrame | np.ndarray) -> pd.DataFrame | np.ndarray:
    """Convert simple returns to log returns: r = ln(1 + R)."""
    return np.log1p(simple_rets)


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------

def resample_log_returns(log_rets: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Resample daily log returns to a coarser frequency by summing.

    Note: this is mathematically correct for log returns. For simple returns
    use `(1 + r).resample(freq).prod() - 1` instead.

    Parameters
    ----------
    freq : pandas offset alias, e.g. "W" (weekly), "ME" (month-end), "QE", "YE"

    Examples
    --------
    >>> daily = to_log_returns(prices)
    >>> weekly = resample_log_returns(daily, "W")
    >>> monthly = resample_log_returns(daily, "ME")
    """
    return log_rets.resample(freq).sum()


# ---------------------------------------------------------------------------
# Compounding / cumulative wealth
# ---------------------------------------------------------------------------

def cumulative_wealth(log_rets: pd.Series | pd.DataFrame, initial: float = 1.0):
    """Build cumulative wealth path from log returns.

    Equivalent to: `np.exp(logrets.cumsum())`.
    """
    return initial * np.exp(log_rets.cumsum())


def total_return(log_rets: pd.Series | pd.DataFrame) -> float | pd.Series:
    """Total simple return over the full sample: exp(sum(r)) - 1."""
    return np.expm1(log_rets.sum())


# ---------------------------------------------------------------------------
# Annualization helpers
# ---------------------------------------------------------------------------

ANNUALIZATION_FACTORS = {
    "1D": 252,
    "D": 252,
    "5D": 51,
    "W": 51,
    "ME": 12,
    "M": 12,
    "QE": 4,
    "Q": 4,
    "YE": 1,
    "Y": 1,
}


def annualize_mean(mean_per_period: float | np.ndarray, freq: str = "D") -> float | np.ndarray:
    """Annualize a per-period mean log return."""
    return mean_per_period * ANNUALIZATION_FACTORS[freq]


def annualize_vol(vol_per_period: float | np.ndarray, freq: str = "D") -> float | np.ndarray:
    """Annualize a per-period volatility (sqrt-of-time rule, with caveat).

    WARNING: sqrt-of-time is only exact for i.i.d. normal log returns.
    For autocorrelated returns it underestimates true annual volatility.
    Use only as a first approximation.
    """
    return vol_per_period * np.sqrt(ANNUALIZATION_FACTORS[freq])


# ---------------------------------------------------------------------------
# Excess returns (vs risk-free)
# ---------------------------------------------------------------------------

def excess_returns(
    log_rets: pd.DataFrame, rf_log_rets: pd.Series | float = 0.0
) -> pd.DataFrame:
    """Subtract risk-free log returns from each asset's log returns.

    If `rf_log_rets` is a scalar, treat as a constant per-period rate.
    """
    if isinstance(rf_log_rets, (int, float)):
        return log_rets - rf_log_rets
    aligned = rf_log_rets.reindex(log_rets.index).fillna(0.0)
    return log_rets.sub(aligned, axis=0)


# ---------------------------------------------------------------------------
# Portfolio returns
# ---------------------------------------------------------------------------

def portfolio_log_returns(
    weights: pd.Series | np.ndarray,
    log_rets: pd.DataFrame,
) -> pd.Series:
    """Compute portfolio log returns given constant weights.

    For static portfolio. For drifting weights (standard backtest),
    use the BacktestEngine instead.
    """
    simple = np.expm1(log_rets)
    port_simple = simple @ np.asarray(weights)
    return np.log1p(port_simple)
