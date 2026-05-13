"""portopt — Portfolio Optimization Toolkit (WCN Softwares).

Based on the course "Portfolio Optimization" by Prof. Guido Chagas (2024).

Quick start:

    >>> import portopt as po
    >>> prices = po.data.load_prices(["PETR4.SA", "VALE3.SA"], start="2020-01-01")
    >>> returns = po.returns.to_log_returns(prices)
    >>> result = po.models.Markowitz().fit(returns, po.ConstraintSet())
    >>> print(result.weights)
"""

from portopt import data, returns, estimators, risk_measures, costs, metrics, viz
from portopt import models
from portopt import datasets
from portopt.models.base import (
    OptimizationModel,
    OptimizationResult,
    ConstraintSet,
)
from portopt.backtest import BacktestEngine, BacktestConfig, BacktestResult
from portopt.compare import compare

__version__ = "0.1.0"

__all__ = [
    "data",
    "returns",
    "estimators",
    "risk_measures",
    "costs",
    "metrics",
    "viz",
    "models",
    "datasets",
    "OptimizationModel",
    "OptimizationResult",
    "ConstraintSet",
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "compare",
]
