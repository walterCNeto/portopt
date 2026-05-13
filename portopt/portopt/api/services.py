"""Service layer — converts API schemas into portopt core calls.

Pattern: the API layer is thin. All it does is:
  1. Validate request (Pydantic handles syntactic).
  2. Translate schema to portopt domain objects.
  3. Invoke portopt core.
  4. Translate result back to schema.

No business logic here; it all lives in portopt core.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

import portopt as po
from portopt import datasets as ds
from portopt.api import schemas as S
from portopt.api.pedagogy import get_pedagogy
from portopt.api.settings import settings
from portopt.costs import (
    B3RealisticCost,
    CompositeCost,
    FlatCost,
    OffshoreCost,
    TaxAwareCost,
    TieredCost,
    ZeroCost,
)
from portopt.models import MODEL_REGISTRY, get_model
from portopt.models.base import ConstraintSet


# ===========================================================================
# Data loading
# ===========================================================================

def load_prices_from_spec(spec: S.DataSpec) -> pd.DataFrame:
    """Resolve a DataSpec to a price DataFrame.

    - source="dataset" → use bundled Chagas datasets
    - source="yfinance" → fetch from Yahoo
    - source="bacen" → fetch BACEN SGS series
    """
    if len(spec.tickers) > settings.max_tickers_per_request:
        raise ValueError(
            f"max {settings.max_tickers_per_request} tickers per request, got {len(spec.tickers)}"
        )

    if spec.source == "dataset":
        if not spec.dataset:
            raise ValueError("source='dataset' requires `dataset` field")
        if spec.subset:
            prices = ds.subset(spec.dataset, spec.subset)
        else:
            prices = ds.load(spec.dataset)
        # Filter requested tickers if a subset was specified by name
        available = [t for t in spec.tickers if t in prices.columns]
        if available:
            prices = prices[available]
        prices = prices.loc[pd.to_datetime(spec.start):]
        if spec.end:
            prices = prices.loc[:pd.to_datetime(spec.end)]
        return prices

    if spec.source == "yfinance":
        return po.data.load_prices(
            spec.tickers, start=spec.start.isoformat(),
            end=spec.end.isoformat() if spec.end else None,
            source="yfinance",
        )

    if spec.source == "bacen":
        return po.data.load_prices(
            spec.tickers, start=spec.start.isoformat(),
            end=spec.end.isoformat() if spec.end else None,
            source="bacen",
        )

    raise ValueError(f"Unsupported data source: {spec.source}")


def to_log_returns(prices: pd.DataFrame, freq: str = "1D") -> pd.DataFrame:
    log_d = po.returns.to_log_returns(prices)
    if freq == "1D":
        return log_d
    if freq == "5D":
        return log_d.iloc[::5]
    if freq == "ME":
        return po.returns.resample_log_returns(log_d, "ME")
    if freq == "QE":
        return po.returns.resample_log_returns(log_d, "QE")
    raise ValueError(f"Unknown frequency: {freq}")


# ===========================================================================
# Constraints translation
# ===========================================================================

def build_constraints(schema: S.ConstraintsSchema, asset_names: list[str]) -> ConstraintSet:
    """Convert API ConstraintsSchema to portopt.ConstraintSet."""
    asset_groups = {}
    group_bounds = {}
    group_risk_budgets = {}
    for g in schema.groups:
        asset_groups[g.name] = g.assets
        if g.min_weight is not None or g.max_weight is not None:
            group_bounds[g.name] = (g.min_weight or 0.0, g.max_weight or 1.0)
        if g.risk_budget is not None:
            group_risk_budgets[g.name] = g.risk_budget

    benchmark = None
    if schema.benchmark_weights:
        benchmark = np.array([
            schema.benchmark_weights.get(name, 0.0) for name in asset_names
        ])

    return ConstraintSet(
        bounds=schema.bounds,
        sum_to=schema.sum_to,
        target_return=schema.target_return,
        target_vol=schema.target_vol,
        target_risk=schema.target_risk,
        risk_aversion=schema.risk_aversion,
        asset_groups=asset_groups,
        group_bounds=group_bounds,
        group_risk_budgets=group_risk_budgets,
        benchmark_weights=benchmark,
    )


# ===========================================================================
# Model instantiation
# ===========================================================================

def build_model(model_name: str, params: S.ModelParams):
    """Instantiate a portopt model given its name and hyperparameters."""
    kwargs: dict[str, Any] = {}

    # CVaR / CDaR
    if params.alpha is not None:
        kwargs["alpha"] = params.alpha
    if params.n_scenarios is not None:
        kwargs["n_scenarios"] = params.n_scenarios

    # IV
    if params.vol_estimator:
        kwargs["vol_estimator"] = params.vol_estimator
    if params.ewma_halflife:
        kwargs["ewma_halflife"] = params.ewma_halflife

    # HRP
    if params.linkage_method:
        kwargs["linkage_method"] = params.linkage_method

    # Utility
    if params.risk_aversion is not None and model_name in ("utility", "quadratic_utility"):
        kwargs["risk_aversion"] = params.risk_aversion

    # Risk Budget
    if params.approach:
        kwargs["approach"] = params.approach

    # Downside Risk
    if params.mar is not None:
        kwargs["mar"] = params.mar

    # MaxSharpe
    if params.risk_free_rate is not None:
        kwargs["risk_free_rate"] = params.risk_free_rate

    # Backend
    if params.backend:
        kwargs["backend"] = params.backend

    # Black-Litterman special: needs market_weights, delta, P, Q
    if model_name in ("black_litterman", "bl"):
        if not params.black_litterman:
            raise ValueError("Black-Litterman requires params.black_litterman")
        bl = params.black_litterman
        # Will be assembled inside the route using asset ordering; for now defer
        return ("bl_deferred", bl, kwargs)

    return get_model(model_name, **kwargs)


def build_black_litterman(
    bl_spec: S.BlackLittermanSpec,
    asset_names: list[str],
    extra_kwargs: dict,
):
    """Special-case constructor for BlackLitterman model."""
    N = len(asset_names)
    K = len(bl_spec.views)

    # Market weights vector
    omega_M = np.array([bl_spec.market_weights.get(a, 0.0) for a in asset_names])

    # Views matrix P (K x N) and Q (K x 1)
    P = np.zeros((K, N))
    Q = np.zeros(K)
    for k, view in enumerate(bl_spec.views):
        for asset, weight in zip(view.assets, view.weights):
            if asset in asset_names:
                P[k, asset_names.index(asset)] = weight
        Q[k] = view.expected

    return po.models.BlackLitterman(
        market_weights=omega_M,
        delta=bl_spec.delta,
        P=P,
        Q=Q,
        tau=bl_spec.tau,
        **extra_kwargs,
    )


# ===========================================================================
# Cost models
# ===========================================================================

def build_cost(spec: S.CostSpec):
    """Translate CostSpec to a portopt CostModel."""
    if spec.kind == "flat":
        rate = (spec.rate_bps or 15.0) / 10_000.0
        return FlatCost(rate=rate)
    if spec.kind == "tiered":
        return TieredCost()
    if spec.kind == "b3_realistic":
        return B3RealisticCost(futures=spec.futures)
    if spec.kind == "offshore":
        return OffshoreCost()
    if spec.kind == "tax_aware":
        kwargs = {}
        if spec.equity_rate is not None:
            kwargs["equity_rate"] = spec.equity_rate
        if spec.fii_rate is not None:
            kwargs["fii_rate"] = spec.fii_rate
        if spec.bond_rate is not None:
            kwargs["bond_rate"] = spec.bond_rate
        return TaxAwareCost(**kwargs)
    if spec.kind == "zero":
        return ZeroCost()
    raise ValueError(f"Unknown cost kind: {spec.kind}")


# ===========================================================================
# Top-level service functions
# ===========================================================================

def run_optimization(req: S.OptimizeRequest) -> S.OptimizationResponse:
    """Execute a single-model optimization."""
    t0 = time.perf_counter()

    prices = load_prices_from_spec(req.data)
    log_rets = to_log_returns(prices, freq=req.data.log_returns_frequency)
    asset_names = list(log_rets.columns)

    constraints = build_constraints(req.constraints, asset_names)

    # Handle Black-Litterman special case
    model_result = build_model(req.model, req.params)
    if isinstance(model_result, tuple) and model_result[0] == "bl_deferred":
        _, bl_spec, extra = model_result
        model = build_black_litterman(bl_spec, asset_names, extra)
    else:
        model = model_result

    result = model.fit(log_rets, constraints)

    canonical_name = MODEL_REGISTRY[req.model.lower()].name \
        if req.model.lower() in MODEL_REGISTRY else req.model
    pedagogy = get_pedagogy(canonical_name)

    return S.OptimizationResponse(
        model=req.model,
        weights={k: float(v) for k, v in result.weights.items()},
        expected_return=result.expected_return,
        risk=float(result.risk),
        risk_measure=result.risk_measure,
        converged=result.converged,
        diagnostics={k: _serialize_diag(v) for k, v in result.diagnostics.items()},
        pedagogy=pedagogy,
        elapsed_ms=(time.perf_counter() - t0) * 1000.0,
    )


def run_backtest(req: S.BacktestRequest, downsample_to: int = 800) -> S.BacktestResponse:
    """Execute a backtest of a single model."""
    t0 = time.perf_counter()

    prices = load_prices_from_spec(req.data)
    if (prices.index[-1] - prices.index[0]).days / 365.25 > settings.max_backtest_years:
        raise ValueError(f"Backtest > {settings.max_backtest_years} years not allowed")

    log_rets = to_log_returns(prices, freq=req.data.log_returns_frequency)
    asset_names = list(log_rets.columns)
    constraints = build_constraints(req.constraints, asset_names)

    model_result = build_model(req.model, req.params)
    if isinstance(model_result, tuple) and model_result[0] == "bl_deferred":
        _, bl_spec, extra = model_result
        model = build_black_litterman(bl_spec, asset_names, extra)
    else:
        model = model_result

    cfg = po.BacktestConfig(
        training_window=req.config.training_window,
        rebalance=req.config.rebalance,
        transaction_costs=build_cost(req.config.cost),
        initial_weights=req.config.initial_weights,
        progress=False,
    )

    engine = po.BacktestEngine(cfg)
    bt = engine.run(prices, model, constraints, log_returns=log_rets)

    # Downsample for transfer (>800 points becomes unwieldy on the wire)
    pts_df = pd.DataFrame({
        "log_return": bt.log_returns,
        "cumulative_wealth": bt.cumulative_wealth,
        "cost_paid": bt.costs_paid,
    })
    if len(pts_df) > downsample_to:
        step = len(pts_df) // downsample_to
        pts_df = pts_df.iloc[::step]

    points = [
        S.BacktestPointSchema(
            date=idx.date(),
            log_return=float(row.log_return),
            cumulative_wealth=float(row.cumulative_wealth),
            cost_paid=float(row.cost_paid),
        )
        for idx, row in pts_df.iterrows()
    ]

    canonical_name = MODEL_REGISTRY[req.model.lower()].name \
        if req.model.lower() in MODEL_REGISTRY else req.model
    pedagogy = get_pedagogy(canonical_name)

    final_weights = bt.weights.iloc[-1]
    return S.BacktestResponse(
        model=req.model,
        points=points,
        rebalance_dates=[d.date() for d in bt.rebalance_dates],
        metrics={k: float(v) for k, v in bt.metrics.items()},
        total_cost_paid=float(bt.costs_paid.sum()),
        weights_at_end={k: float(v) for k, v in final_weights.items() if abs(v) > 1e-6},
        pedagogy=pedagogy,
        elapsed_ms=(time.perf_counter() - t0) * 1000.0,
    )


def run_compare(req: S.CompareRequest) -> S.CompareResponse:
    """Run multiple models on the same dataset."""
    t0 = time.perf_counter()

    prices = load_prices_from_spec(req.data)
    log_rets = to_log_returns(prices, freq=req.data.log_returns_frequency)
    asset_names = list(log_rets.columns)
    constraints = build_constraints(req.constraints, asset_names)

    optimizations: dict[str, S.OptimizationResponse] = {}
    backtests: dict[str, S.BacktestResponse] = {}
    summary_rows: list[dict] = []
    weights_table: dict[str, dict[str, float]] = {n: {} for n in asset_names}

    for spec in req.models:
        opt_req = S.OptimizeRequest(
            model=spec.model, data=req.data, constraints=req.constraints, params=spec.params,
        )
        try:
            opt = run_optimization(opt_req)
            optimizations[spec.model] = opt
            for asset, w in opt.weights.items():
                weights_table.setdefault(asset, {})[spec.model] = w
            summary_rows.append({
                "model": spec.model,
                "expected_return": opt.expected_return,
                "risk": opt.risk,
                "risk_measure": opt.risk_measure,
                "converged": opt.converged,
                "n_active": sum(1 for w in opt.weights.values() if abs(w) > 1e-6),
                "max_weight": max(opt.weights.values()) if opt.weights else 0.0,
            })
        except Exception as e:
            summary_rows.append({"model": spec.model, "error": str(e)})

        if req.with_backtest:
            bt_req = S.BacktestRequest(
                model=spec.model, data=req.data, constraints=req.constraints,
                params=spec.params,
                config=req.backtest_config or S.BacktestConfigSchema(),
            )
            try:
                backtests[spec.model] = run_backtest(bt_req)
            except Exception:
                pass

    return S.CompareResponse(
        optimizations=optimizations,
        backtests=backtests if req.with_backtest else None,
        summary_table=summary_rows,
        weights_table=weights_table,
        elapsed_ms=(time.perf_counter() - t0) * 1000.0,
    )


# ===========================================================================
# Internal helpers
# ===========================================================================

def _serialize_diag(v: Any) -> Any:
    """Make diagnostics JSON-serializable."""
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (list, tuple)):
        return [_serialize_diag(x) for x in v]
    if isinstance(v, dict):
        return {k: _serialize_diag(x) for k, x in v.items()}
    return str(v)
