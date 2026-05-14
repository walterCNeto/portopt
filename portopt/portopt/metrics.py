"""Performance and risk metrics.

The standard `quantstats` equivalent: Sharpe, Sortino, Calmar, Omega,
max drawdown, ulcer index, etc. Used for backtest reporting and for the
comparative analysis (which is the differentiating feature of the product).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Return-based metrics
# ---------------------------------------------------------------------------

def total_return(log_rets: pd.Series) -> float:
    """exp(sum) - 1."""
    return float(np.expm1(log_rets.sum()))


def annualized_return(log_rets: pd.Series, periods_per_year: int = 252) -> float:
    """Geometric annualized return."""
    if len(log_rets) == 0:
        return 0.0
    avg_log = log_rets.mean()
    return float(np.expm1(avg_log * periods_per_year))


def annualized_vol(log_rets: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized volatility (sqrt-of-time)."""
    return float(log_rets.std() * np.sqrt(periods_per_year))


def sharpe_ratio(
    log_rets: pd.Series, risk_free: float = 0.0, periods_per_year: int = 252
) -> float:
    """Annualized Sharpe = (avg excess return) / std × √periods.

    `risk_free` is per-period (i.e. daily if log_rets is daily). For an annual
    risk-free rate r_a, pass r_a/periods_per_year.
    """
    excess = log_rets - risk_free
    std = excess.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def sortino_ratio(
    log_rets: pd.Series, mar: float = 0.0, periods_per_year: int = 252
) -> float:
    """Sortino: (mean - MAR) / downside_std × √periods."""
    excess = log_rets - mar
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf")
    dd_std = np.sqrt((downside ** 2).mean())
    if dd_std == 0:
        return 0.0
    return float(excess.mean() / dd_std * np.sqrt(periods_per_year))


def calmar_ratio(log_rets: pd.Series, periods_per_year: int = 252) -> float:
    """Calmar = annualized return / |max drawdown|."""
    mdd = max_drawdown(log_rets)
    if mdd == 0:
        return 0.0
    return float(annualized_return(log_rets, periods_per_year) / abs(mdd))


def omega_ratio(log_rets: pd.Series, mar: float = 0.0) -> float:
    """Omega = E[max(R - MAR, 0)] / E[max(MAR - R, 0)]."""
    excess = log_rets - mar
    up = np.maximum(excess, 0).sum()
    down = -np.minimum(excess, 0).sum()
    if down == 0:
        return float("inf")
    return float(up / down)


# ---------------------------------------------------------------------------
# Drawdown metrics
# ---------------------------------------------------------------------------

def drawdown_series(log_rets: pd.Series) -> pd.Series:
    """Drawdown series from cumulative log returns.

    Returns negative values (or zero at peaks). Computed on compounded wealth.
    """
    cum = np.exp(log_rets.cumsum())
    running_max = cum.cummax()
    return cum / running_max - 1.0


def max_drawdown(log_rets: pd.Series) -> float:
    """Worst peak-to-trough drawdown (a non-positive number)."""
    if len(log_rets) == 0:
        return 0.0
    return float(drawdown_series(log_rets).min())


def avg_drawdown(log_rets: pd.Series) -> float:
    """Average of all drawdowns (negative number)."""
    dd = drawdown_series(log_rets)
    troughs = dd[dd < 0]
    return float(troughs.mean()) if len(troughs) > 0 else 0.0


def ulcer_index(log_rets: pd.Series) -> float:
    """Ulcer Index: RMS of drawdowns (Martin & McCann 1989).

    Penalizes both depth and duration. Lower is better.
    """
    dd = drawdown_series(log_rets) * 100  # in %
    return float(np.sqrt((dd ** 2).mean()))


# ---------------------------------------------------------------------------
# Tail risk metrics
# ---------------------------------------------------------------------------

def value_at_risk(log_rets: pd.Series, alpha: float = 0.05) -> float:
    """Historical VaR at significance α (positive number = loss magnitude)."""
    if len(log_rets) == 0:
        return 0.0
    return float(-np.quantile(log_rets, alpha))


def conditional_value_at_risk(log_rets: pd.Series, alpha: float = 0.05) -> float:
    """Historical CVaR / Expected Shortfall (positive number = loss magnitude)."""
    if len(log_rets) == 0:
        return 0.0
    q = np.quantile(log_rets, alpha)
    tail = log_rets[log_rets <= q]
    if len(tail) == 0:
        return float(-q)
    return float(-tail.mean())


def skewness(log_rets: pd.Series) -> float:
    """Excess skewness (Fisher-Pearson)."""
    if len(log_rets) < 3:
        return 0.0
    return float(log_rets.skew())


def kurtosis(log_rets: pd.Series) -> float:
    """Excess kurtosis (Fisher: normal = 0)."""
    if len(log_rets) < 4:
        return 0.0
    return float(log_rets.kurt())


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def compute_summary_metrics(
    log_rets: pd.Series,
    risk_free: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """One-call summary, ready for display."""
    return {
        "total_return": total_return(log_rets),
        "annualized_return": annualized_return(log_rets, periods_per_year),
        "annualized_vol": annualized_vol(log_rets, periods_per_year),
        "sharpe": sharpe_ratio(log_rets, risk_free, periods_per_year),
        "sortino": sortino_ratio(log_rets, periods_per_year=periods_per_year),
        "calmar": calmar_ratio(log_rets, periods_per_year),
        "omega": omega_ratio(log_rets),
        "max_drawdown": max_drawdown(log_rets),
        "ulcer_index": ulcer_index(log_rets),
        "var_5%": value_at_risk(log_rets, 0.05),
        "cvar_5%": conditional_value_at_risk(log_rets, 0.05),
        "skewness": skewness(log_rets),
        "kurtosis": kurtosis(log_rets),
    }


def metrics_to_dataframe(metrics: dict | list[dict], labels: list[str] | None = None) -> pd.DataFrame:
    """Convert metrics dict(s) to a pretty DataFrame for display."""
    if isinstance(metrics, dict):
        return pd.DataFrame.from_dict(metrics, orient="index", columns=["value"])
    df = pd.DataFrame(metrics)
    if labels:
        df.index = labels
    return df.T
