"""Visualization helpers.

Functions are pure-matplotlib for compatibility with notebooks (Chagas style).
A Plotly variant for the future web UI can be added in `viz_plotly.py`.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def plot_efficient_frontier(
    risks: list[float],
    returns: list[float],
    labels: Optional[list[str]] = None,
    ax=None,
    show_points: bool = True,
):
    """Plot a (risk, return) efficient frontier.

    Risks are in the model's native unit (vol, MAD, CVaR, ...).
    """
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4))
    ax.plot(risks, returns, marker="o" if show_points else None, linewidth=1.5)
    if labels:
        for x, y, lbl in zip(risks, returns, labels):
            ax.annotate(lbl, (x, y), fontsize=7, xytext=(5, 5), textcoords="offset points")
    ax.set_xlabel("Risk")
    ax.set_ylabel("Expected Return")
    ax.set_title("Efficient Frontier")
    ax.grid(True, linestyle="--", linewidth=0.5)
    return ax


def plot_allocation_area(weights: pd.DataFrame, ax=None):
    """Stacked area plot of portfolio allocation over time."""
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 4))
    weights.plot.area(ax=ax, stacked=True, colormap="terrain_r", legend=False)
    ax.set_xlim(weights.index[0], weights.index[-1])
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Allocation over time")
    return ax


def plot_risk_contributions_area(
    weights: pd.DataFrame,
    log_returns: pd.DataFrame,
    rolling_window: int = 252,
    ax=None,
):
    """Stacked-area of percentual risk contributions over time."""
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 4))

    rc_pct = pd.DataFrame(index=weights.index, columns=weights.columns, dtype=float)
    for dt in weights.index[rolling_window:]:
        window = log_returns.loc[:dt].iloc[-rolling_window:]
        cov = window.cov().values
        w = weights.loc[dt].values
        vol = float(np.sqrt(max(w @ cov @ w, 0.0)))
        if vol > 0:
            rc = w * (cov @ w) / vol
            rc_pct.loc[dt, :] = np.clip(rc / rc.sum(), 0.0, np.inf)
        else:
            rc_pct.loc[dt, :] = 0.0

    rc_pct.dropna().plot.area(ax=ax, stacked=True, colormap="terrain_r", legend=False)
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Risk Contributions (%) over time")
    return ax


def plot_cumulative_wealth(
    wealth_paths: pd.DataFrame | dict[str, pd.Series],
    title: str = "Cumulative Performance",
    ax=None,
):
    """Compare cumulative wealth paths from multiple backtests."""
    import matplotlib.pyplot as plt
    if isinstance(wealth_paths, dict):
        wealth_paths = pd.DataFrame(wealth_paths)
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 4))
    wealth_paths.plot(ax=ax, linewidth=1.2)
    ax.set_xlim(wealth_paths.index[0], wealth_paths.index[-1])
    ax.set_title(title)
    ax.grid(True, linestyle="--", linewidth=0.5)
    ax.legend(framealpha=1.0)
    return ax


def plot_drawdown(log_rets: pd.Series, ax=None):
    """Drawdown plot (negative values, area filled)."""
    import matplotlib.pyplot as plt
    cum = np.exp(log_rets.cumsum())
    dd = cum / cum.cummax() - 1.0
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 3))
    ax.fill_between(dd.index, dd.values, 0, color="red", alpha=0.3)
    ax.plot(dd.index, dd.values, color="red", linewidth=0.8)
    ax.set_ylim(dd.min() * 1.1, 0.01)
    ax.set_title("Drawdown")
    ax.grid(True, linestyle="--", linewidth=0.5)
    return ax


def plot_hrp_dendrogram(linkages: np.ndarray, labels: list[str], ax=None):
    """HRP dendrogram (Chagas nb3 cell 60)."""
    import matplotlib.pyplot as plt
    import scipy.cluster.hierarchy as sch
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4))
    sch.dendrogram(linkages, leaf_rotation=90, leaf_font_size=6, labels=labels, ax=ax)
    ax.set_title("HRP Hierarchical Clustering")
    return ax
