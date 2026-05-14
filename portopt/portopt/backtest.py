"""Generic backtest engine.

This is the *core abstraction*. It replicates the loop that appears identically
in all 4 reference notebooks (load → drift weights daily → rebalance monthly →
apply transaction costs), but with the optimization step *factored out as a
plugin*.

Standard backtest pattern:

    for i in range(T_training+1, T):
        rets = expm1(logrets.loc[curr_date])
        for each model:
            # 1) drift weights by realized returns
            adj_ws = old_ws * (1 + rets)
            new_ws = adj_ws / sum(adj_ws)
            # 2) compute portfolio log return
            port_logret = log1p(sum(old_ws * rets))
            # 3) if rebalance date:
            if curr_date in rebal_dates:
                mu, cov = estimate_from_window(logrets[i-T_training:i])
                new_ws = optimizer.fit(...)
                cost = transaction_cost(old_ws, new_ws)
                port_logret -= log1p(cost)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Union

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from portopt.costs import CostModel, FlatCost
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


# ---------------------------------------------------------------------------
# Rebalancing schedule
# ---------------------------------------------------------------------------

def monthly_rebal_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Last business day of each month. Standard convention:

        port_ws.groupby(port_ws.index.to_period('M')).apply(lambda d: d.index.max())
    """
    s = pd.Series(index=index, dtype=float)
    return s.groupby(s.index.to_period("M")).apply(lambda d: d.index.max()).tolist()


def weekly_rebal_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    s = pd.Series(index=index, dtype=float)
    return s.groupby(s.index.to_period("W")).apply(lambda d: d.index.max()).tolist()


def quarterly_rebal_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    s = pd.Series(index=index, dtype=float)
    return s.groupby(s.index.to_period("Q")).apply(lambda d: d.index.max()).tolist()


REBAL_SCHEDULES = {
    "monthly": monthly_rebal_dates,
    "weekly": weekly_rebal_dates,
    "quarterly": quarterly_rebal_dates,
}


def resolve_rebal_dates(
    spec: Union[str, Callable[[pd.DatetimeIndex], list]],
    index: pd.DatetimeIndex,
) -> list[pd.Timestamp]:
    if callable(spec):
        return spec(index)
    if spec in REBAL_SCHEDULES:
        return REBAL_SCHEDULES[spec](index)
    raise ValueError(f"Unknown rebalance schedule: {spec!r}. Options: {list(REBAL_SCHEDULES)}")


# ---------------------------------------------------------------------------
# Config / Result
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    """Configuration for a backtest run.

    Attributes
    ----------
    training_window : int
        Number of past observations used to estimate μ, Σ at each rebalance.
        Common values: 252 (1y daily), 1260 (5y daily), 60 (5y monthly).
    rebalance : str or callable
        "monthly", "weekly", "quarterly", or a function index -> list[Timestamp].
    transaction_costs : CostModel
        Cost model applied at each rebalancing date.
    initial_weights : "equal" or "zero" or "first_alloc"
        How to initialize port weights before first rebal.
        "first_alloc" delays cost-incurring rebal to the first opt date.
    skip_first_rebal_costs : bool
        Whether to skip costs on the very first rebalancing date.
        For BH this is implicit (BH rebalances only once).
    progress : bool
        Show tqdm progress bar.
    """

    training_window: int = 252
    rebalance: Union[str, Callable] = "monthly"
    transaction_costs: CostModel = field(default_factory=lambda: FlatCost(rate=0.0015))
    initial_weights: str = "first_alloc"
    skip_first_rebal_costs: bool = False
    progress: bool = True


@dataclass
class BacktestResult:
    """Output of a backtest run.

    Attributes
    ----------
    weights : pd.DataFrame
        T × N matrix of portfolio weights over time.
    log_returns : pd.Series
        T-length series of portfolio log returns (net of costs).
    cumulative_wealth : pd.Series
        exp(cumsum(log_returns)), normalized to start at 1.
    rebalance_dates : list of Timestamps
    costs_paid : pd.Series
        Cost incurred at each rebalance date (0 elsewhere).
    opt_results : dict[Timestamp, OptimizationResult]
        Full OptimizationResult for each rebalance date.
    metrics : dict
        Summary metrics (Sharpe, vol, max DD, etc.).
    """

    weights: pd.DataFrame
    log_returns: pd.Series
    cumulative_wealth: pd.Series
    rebalance_dates: list[pd.Timestamp]
    costs_paid: pd.Series
    opt_results: dict[pd.Timestamp, OptimizationResult] = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        n_rebal = len(self.rebalance_dates)
        total_ret = float(np.exp(self.log_returns.sum()) - 1)
        return (
            f"BacktestResult(periods={len(self.log_returns)}, rebalances={n_rebal}, "
            f"total_return={total_ret:.2%}, sharpe={self.metrics.get('sharpe', float('nan')):.3f})"
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """Generic backtest engine. Accepts ANY OptimizationModel.

    The engine is *look-ahead bias proof by design*: at time t, the model only
    receives `log_returns.iloc[i - training_window : i]`, never future data.
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        prices: pd.DataFrame,
        model: OptimizationModel,
        constraints: ConstraintSet,
        log_returns: Optional[pd.DataFrame] = None,
    ) -> BacktestResult:
        """Run the backtest.

        Parameters
        ----------
        prices : pd.DataFrame
            T x N adjusted close prices (used to compute returns if log_returns
            is not provided).
        model : OptimizationModel
            Any portopt model. The engine doesn't care which one.
        constraints : ConstraintSet
        log_returns : pd.DataFrame, optional
            Pre-computed log returns. If None, computed from prices.

        Returns
        -------
        BacktestResult
        """
        cfg = self.config

        if log_returns is None:
            log_returns = np.log1p(prices.pct_change()).dropna()
        log_returns = log_returns.copy()

        T, N = log_returns.shape
        if T <= cfg.training_window + 1:
            raise ValueError(
                f"Need at least training_window+2 observations, got T={T}, window={cfg.training_window}"
            )

        start_i = cfg.training_window + 1
        prev_i = start_i - 1
        names = log_returns.columns.tolist()

        # Pre-allocate output frames
        idx = log_returns.index[prev_i:T]
        weights = pd.DataFrame(0.0, index=idx, columns=names, dtype=float)
        port_logrets = pd.Series(0.0, index=idx, dtype=float)
        costs_paid = pd.Series(0.0, index=idx, dtype=float)
        opt_results: dict[pd.Timestamp, OptimizationResult] = {}

        rebal_dates = resolve_rebal_dates(cfg.rebalance, log_returns.index[prev_i:T])
        rebal_set = set(rebal_dates)

        prev_date = log_returns.index[prev_i]
        first_rebal = True

        iterator = range(start_i, T)
        if cfg.progress:
            iterator = tqdm(iterator, desc=f"Backtest {model.name}")

        for i in iterator:
            curr_date = log_returns.index[i]
            rets = np.expm1(log_returns.loc[curr_date].values)
            old_w = weights.loc[prev_date].values

            # ---- 1. Portfolio return for the day (using yesterday's weights)
            port_simple = float(np.sum(old_w * rets))
            port_logrets.loc[curr_date] = float(np.log1p(port_simple))

            # ---- 2. Drift weights to current date
            adj = old_w * (1.0 + rets)
            total = float(adj.sum())
            if total > 0:
                weights.loc[curr_date, :] = adj / total
            else:
                weights.loc[curr_date, :] = 0.0

            # ---- 3. Rebalance if today is a rebal date
            if curr_date in rebal_set:
                window = log_returns.iloc[i - cfg.training_window - 1 : i - 1]
                try:
                    opt_res = model.fit(window, constraints)
                    opt_results[curr_date] = opt_res
                    new_w = opt_res.weights.reindex(names).fillna(0.0).values
                except Exception as e:  # pragma: no cover
                    # If model fails, hold the current weights
                    new_w = weights.loc[curr_date, :].values
                    opt_results[curr_date] = None

                old_after_drift = weights.loc[curr_date, :].values

                # Skip cost on very first rebal if requested
                if not (cfg.skip_first_rebal_costs and first_rebal):
                    c = cfg.transaction_costs.cost(
                        current_weights=old_after_drift,
                        new_weights=new_w,
                        dt=curr_date,
                    )
                    costs_paid.loc[curr_date] = c
                    port_logrets.loc[curr_date] -= float(np.log1p(c))

                weights.loc[curr_date, :] = new_w
                first_rebal = False

            prev_date = curr_date

        # Cumulative wealth (standard: np.exp(cumsum))
        cum = np.exp(port_logrets.cumsum())

        result = BacktestResult(
            weights=weights,
            log_returns=port_logrets,
            cumulative_wealth=cum,
            rebalance_dates=rebal_dates,
            costs_paid=costs_paid,
            opt_results=opt_results,
        )
        # Attach quick metrics
        from portopt.metrics import compute_summary_metrics
        result.metrics = compute_summary_metrics(port_logrets, periods_per_year=252)
        return result
