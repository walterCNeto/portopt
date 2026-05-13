"""Compare multiple optimization models on the same dataset.

This is the differentiating feature of the product: run the entire Chagas menu
on the same prices, with the same constraints, and present a unified comparison
of weights, risks, expected returns and (optionally) full backtests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

import numpy as np
import pandas as pd

from portopt.backtest import BacktestConfig, BacktestEngine, BacktestResult
from portopt.metrics import metrics_to_dataframe
from portopt.models import MODEL_REGISTRY, get_model
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


@dataclass
class ComparisonResult:
    """Side-by-side comparison of multiple models."""

    optimizations: dict[str, OptimizationResult] = field(default_factory=dict)
    backtests: dict[str, BacktestResult] = field(default_factory=dict)
    constraints: Optional[ConstraintSet] = None

    # -------- Display helpers --------

    def weights_table(self) -> pd.DataFrame:
        """N x M DataFrame of weights, one column per model."""
        if not self.optimizations:
            return pd.DataFrame()
        return pd.DataFrame({k: v.weights for k, v in self.optimizations.items()})

    def summary_table(self) -> pd.DataFrame:
        """One-row-per-model summary: expected return, risk (native), risk_measure."""
        if not self.optimizations:
            return pd.DataFrame()
        rows = []
        for name, opt in self.optimizations.items():
            rows.append({
                "model": name,
                "expected_return": opt.expected_return,
                "risk": opt.risk,
                "risk_measure": opt.risk_measure,
                "converged": opt.converged,
                "n_active_positions": int((opt.weights.abs() > 1e-6).sum()),
                "max_weight": float(opt.weights.max()),
                "min_weight": float(opt.weights.min()),
            })
        return pd.DataFrame(rows).set_index("model")

    def metrics_table(self) -> pd.DataFrame:
        """Backtest performance metrics, one column per model."""
        if not self.backtests:
            return pd.DataFrame()
        rows = {k: bt.metrics for k, bt in self.backtests.items()}
        return pd.DataFrame(rows)

    def cumulative_wealth(self) -> pd.DataFrame:
        """Cumulative wealth paths, one column per model (only if backtested)."""
        if not self.backtests:
            return pd.DataFrame()
        return pd.DataFrame({k: bt.cumulative_wealth for k, bt in self.backtests.items()})

    def __repr__(self) -> str:
        opts = list(self.optimizations.keys())
        return f"ComparisonResult(models={opts}, with_backtest={bool(self.backtests)})"


def compare(
    models: list[Union[str, OptimizationModel]],
    prices: pd.DataFrame,
    constraints: Optional[ConstraintSet] = None,
    log_returns: Optional[pd.DataFrame] = None,
    with_backtest: bool = False,
    backtest_config: Optional[BacktestConfig] = None,
    model_kwargs: Optional[dict[str, dict]] = None,
) -> ComparisonResult:
    """Run the same dataset through multiple models and return a comparison.

    Parameters
    ----------
    models : list of model names or instances
        Strings are resolved via MODEL_REGISTRY; instances are used as-is.
    prices : pd.DataFrame
    constraints : ConstraintSet, optional
        Default: long-only sum-to-one.
    log_returns : pd.DataFrame, optional
        Pre-computed log returns. If None, computed from prices.
    with_backtest : bool
        If True, run the full BacktestEngine for each model.
    backtest_config : BacktestConfig, optional
    model_kwargs : dict, optional
        Per-model constructor kwargs, e.g. {"hrp": {"linkage_method": "ward"}}.

    Examples
    --------
    >>> result = compare(
    ...     models=["markowitz", "hrp", "cvar", "ew"],
    ...     prices=prices,
    ...     constraints=ConstraintSet(bounds=(0.0, 0.4)),
    ...     with_backtest=True,
    ... )
    >>> print(result.summary_table())
    >>> print(result.metrics_table())
    """
    constraints = constraints or ConstraintSet()
    model_kwargs = model_kwargs or {}

    if log_returns is None:
        log_returns = np.log1p(prices.pct_change()).dropna()

    result = ComparisonResult(constraints=constraints)

    for spec in models:
        if isinstance(spec, str):
            kwargs = model_kwargs.get(spec, {})
            try:
                model = get_model(spec, **kwargs)
            except TypeError:
                # Some models (e.g. BlackLitterman) require positional kwargs
                # the caller is responsible for passing via model_kwargs.
                raise
            model_name = spec
        else:
            model = spec
            model_name = getattr(model, "name", model.__class__.__name__)

        # 1. Optimize once on the full sample
        try:
            opt = model.fit(log_returns, constraints)
            result.optimizations[model_name] = opt
        except NotImplementedError as e:
            print(f"[skip] {model_name}: {e}")
            continue
        except Exception as e:
            print(f"[error] {model_name}: {e}")
            continue

        # 2. Optionally run full backtest
        if with_backtest:
            try:
                cfg = backtest_config or BacktestConfig(progress=False)
                engine = BacktestEngine(cfg)
                bt = engine.run(prices, model, constraints, log_returns=log_returns)
                result.backtests[model_name] = bt
            except Exception as e:
                print(f"[backtest error] {model_name}: {e}")

    return result
