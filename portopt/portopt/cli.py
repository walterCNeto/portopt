"""CLI — the "menu" interface.

Exposes the model menu as a command-line tool, mirroring the future
web UI / API. Provides three main verbs: list, optimize, backtest, compare.

Usage:
    portopt list-models
    portopt optimize --model hrp --tickers PETR4.SA,VALE3.SA,ITUB4.SA --start 2020-01-01
    portopt backtest --model markowitz --tickers SPY,QQQ,GLD --start 2018-01-01 --cost flat:15
    portopt compare --models markowitz,hrp,erc,cvar --tickers SPY,QQQ,IWM,GLD
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_tickers(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


def parse_bounds(s: str) -> tuple[float, float]:
    """Parse '0,0.4' -> (0.0, 0.4)."""
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 2:
        raise ValueError(f"bounds must be 'lower,upper', got {s!r}")
    return (parts[0], parts[1])


def parse_cost(s: str):
    """Parse cost spec.

    Examples:
        "flat:15"      -> FlatCost(rate=0.0015)         (15 bps)
        "flat:2"       -> FlatCost(rate=0.0002)         (2 bps)
        "b3"           -> B3RealisticCost()
        "b3:futures"   -> B3RealisticCost(futures=True)
        "offshore"     -> OffshoreCost()
        "zero"         -> ZeroCost()
    """
    from portopt.costs import FlatCost, B3RealisticCost, OffshoreCost, ZeroCost
    if ":" in s:
        name, arg = s.split(":", 1)
    else:
        name, arg = s, ""
    name = name.lower()

    if name == "flat":
        bps = float(arg) if arg else 15.0
        return FlatCost(rate=bps / 10_000.0)
    if name == "b3":
        return B3RealisticCost(futures=(arg == "futures"))
    if name == "offshore":
        return OffshoreCost()
    if name == "zero":
        return ZeroCost()
    raise ValueError(f"Unknown cost: {s!r}")


def load_prices_cmd(tickers: list[str], start: str, end: Optional[str], source: str):
    from portopt import data as portopt_data
    print(f"[data] Loading {len(tickers)} tickers from {source}...", file=sys.stderr)
    return portopt_data.load_prices(tickers, start=start, end=end, source=source)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list_models(args):
    """portopt list-models"""
    from portopt.models import MODEL_REGISTRY
    # Group by canonical class so aliases don't clutter
    seen = {}
    for alias, cls in MODEL_REGISTRY.items():
        seen.setdefault(cls, []).append(alias)

    print("Available models (canonical name | aliases | risk measure | needs returns):")
    print("-" * 86)
    for cls, aliases in seen.items():
        canonical = cls.name if hasattr(cls, "name") else cls.__name__
        aliases_clean = [a for a in aliases if a != canonical]
        ali = ",".join(aliases_clean) if aliases_clean else "—"
        print(f"  {canonical:24s} | {ali:24s} | {cls.native_risk_measure:14s} | {cls.requires_returns}")


def cmd_optimize(args):
    """portopt optimize ..."""
    from portopt import ConstraintSet
    from portopt.models import get_model

    prices = load_prices_cmd(parse_tickers(args.tickers), args.start, args.end, args.source)
    log_rets = np.log1p(prices.pct_change()).dropna()

    constraints = ConstraintSet(
        bounds=parse_bounds(args.bounds),
        sum_to=1.0,
        target_return=args.target_return,
        target_vol=args.target_vol,
    )

    model = get_model(args.model)
    result = model.fit(log_rets, constraints)

    print()
    print(f"Model:        {args.model}")
    print(f"Risk measure: {result.risk_measure}")
    print(f"Risk:         {result.risk:.6f}")
    if result.expected_return is not None:
        print(f"E[R] (per d): {result.expected_return:.6f}")
        print(f"E[R] (annl):  {(np.exp(result.expected_return * 252) - 1):.4%}")
    print(f"Converged:    {result.converged}")
    print()
    print("Weights:")
    print(result.weights.sort_values(ascending=False).to_string(float_format="%.4f"))


def cmd_backtest(args):
    """portopt backtest ..."""
    from portopt import ConstraintSet, BacktestConfig, BacktestEngine
    from portopt.models import get_model

    prices = load_prices_cmd(parse_tickers(args.tickers), args.start, args.end, args.source)

    constraints = ConstraintSet(
        bounds=parse_bounds(args.bounds),
        target_return=args.target_return,
        target_vol=args.target_vol,
    )
    cost = parse_cost(args.cost)

    cfg = BacktestConfig(
        training_window=args.training_window,
        rebalance=args.rebalance,
        transaction_costs=cost,
        progress=True,
    )
    model = get_model(args.model)
    engine = BacktestEngine(cfg)
    result = engine.run(prices, model, constraints)

    print()
    print(f"Model:    {args.model}")
    print(f"Periods:  {len(result.log_returns)}")
    print(f"Rebals:   {len(result.rebalance_dates)}")
    print(f"Costs:    R${(result.costs_paid.sum() * 100):.4f}% of initial NAV")
    print()
    print("Metrics:")
    for k, v in result.metrics.items():
        if isinstance(v, float):
            fmt = "%.4%" if "return" in k or "drawdown" in k or "var" in k or "vol" in k else "%.4f"
            print(f"  {k:22s} = {fmt % v}")
        else:
            print(f"  {k:22s} = {v}")

    if args.output:
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        result.weights.to_parquet(out / "weights.parquet")
        result.log_returns.to_frame("log_return").to_parquet(out / "log_returns.parquet")
        result.cumulative_wealth.to_frame("cumulative_wealth").to_parquet(out / "wealth.parquet")
        with (out / "metrics.json").open("w") as f:
            json.dump(result.metrics, f, indent=2, default=str)
        print(f"\nSaved outputs to: {out}/")


def cmd_compare(args):
    """portopt compare ..."""
    from portopt import ConstraintSet, BacktestConfig
    from portopt.compare import compare

    prices = load_prices_cmd(parse_tickers(args.tickers), args.start, args.end, args.source)
    constraints = ConstraintSet(
        bounds=parse_bounds(args.bounds),
        target_return=args.target_return,
        target_vol=args.target_vol,
    )
    cost = parse_cost(args.cost) if args.cost else None
    bt_cfg = BacktestConfig(
        training_window=args.training_window,
        rebalance=args.rebalance,
        transaction_costs=cost,
        progress=True,
    ) if cost else None

    models = parse_tickers(args.models)
    result = compare(
        models=models,
        prices=prices,
        constraints=constraints,
        with_backtest=args.with_backtest,
        backtest_config=bt_cfg,
    )

    print("\n=== Allocation summary ===")
    print(result.summary_table().to_string(float_format="%.4f"))
    print("\n=== Weights ===")
    print(result.weights_table().to_string(float_format="%.4f"))

    if args.with_backtest:
        print("\n=== Backtest metrics ===")
        print(result.metrics_table().to_string(float_format="%.4f"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="portopt",
        description="Portfolio Optimization Toolkit (WCN Softwares)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # list-models
    pl = sub.add_parser("list-models", help="List available optimization models")
    pl.set_defaults(func=cmd_list_models)

    # common args
    def add_common(sp):
        sp.add_argument("--tickers", required=True, help="Comma-separated list")
        sp.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
        sp.add_argument("--end", default=None, help="End date YYYY-MM-DD")
        sp.add_argument("--source", default="yfinance", choices=["yfinance", "excel", "bacen"])
        sp.add_argument("--bounds", default="0,1", help="Lower,upper allocation bounds")
        sp.add_argument("--target-return", type=float, default=None)
        sp.add_argument("--target-vol", type=float, default=None)

    # optimize
    po = sub.add_parser("optimize", help="Run a single-model optimization on the full sample")
    add_common(po)
    po.add_argument("--model", required=True, help="Model name (see list-models)")
    po.set_defaults(func=cmd_optimize)

    # backtest
    pb = sub.add_parser("backtest", help="Run a rolling backtest of a single model")
    add_common(pb)
    pb.add_argument("--model", required=True)
    pb.add_argument("--training-window", type=int, default=252)
    pb.add_argument("--rebalance", default="monthly", choices=["monthly", "weekly", "quarterly"])
    pb.add_argument("--cost", default="flat:15", help="Cost spec, e.g. 'flat:15', 'b3', 'zero'")
    pb.add_argument("--output", default=None, help="Directory to save parquet outputs")
    pb.set_defaults(func=cmd_backtest)

    # compare
    pc = sub.add_parser("compare", help="Compare several models on the same dataset")
    add_common(pc)
    pc.add_argument("--models", required=True, help="Comma-separated model names")
    pc.add_argument("--with-backtest", action="store_true", help="Also run backtests")
    pc.add_argument("--training-window", type=int, default=252)
    pc.add_argument("--rebalance", default="monthly")
    pc.add_argument("--cost", default="flat:15")
    pc.set_defaults(func=cmd_compare)

    return p


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
