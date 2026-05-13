"""Optimization models, organized by tier of complexity.

The `MODEL_REGISTRY` maps short string names to model classes, used by:
- CLI (`portopt optimize --model hrp`)
- API endpoints (`POST /optimize {"model": "hrp", ...}`)
- Frontend menu
"""

from __future__ import annotations

from portopt.models.base import (
    OptimizationModel,
    OptimizationResult,
    ConstraintSet,
    Backend,
)

# Tier 0 — Naïve
from portopt.models.naive import EqualWeight, BuyAndHold, InverseVolatility

# Tier 1 — Allocation-based (Markowitz family)
from portopt.models.markowitz import Markowitz, MinimumVariance, MaximumSharpe
from portopt.models.utility import QuadraticUtility

# Tier 2 — Alternative Risk Measures
from portopt.models.mad import MAD
from portopt.models.tracking import TrackingError
from portopt.models.downside import DownsideRisk
from portopt.models.cvar import CVaR
from portopt.models.cdar import CDaR

# Tier 3 — Risk Budgeting
from portopt.models.erc import EqualRiskContribution
from portopt.models.risk_budget import RiskBudget
from portopt.models.hrp import HierarchicalRiskParity

# Tier 4 — Robust (Bayesian)
from portopt.models.black_litterman import BlackLitterman


MODEL_REGISTRY: dict[str, type[OptimizationModel]] = {
    # Tier 0
    "equal_weight": EqualWeight,
    "ew": EqualWeight,
    "buy_and_hold": BuyAndHold,
    "bh": BuyAndHold,
    "inverse_vol": InverseVolatility,
    "iv": InverseVolatility,

    # Tier 1
    "markowitz": Markowitz,
    "mv": Markowitz,
    "min_var": MinimumVariance,
    "mvp": MinimumVariance,
    "max_sharpe": MaximumSharpe,
    "tangency": MaximumSharpe,
    "utility": QuadraticUtility,

    # Tier 2
    "mad": MAD,
    "tracking_error": TrackingError,
    "te": TrackingError,
    "downside_risk": DownsideRisk,
    "dr": DownsideRisk,
    "cvar": CVaR,
    "cdar": CDaR,

    # Tier 3
    "erc": EqualRiskContribution,
    "risk_parity": EqualRiskContribution,
    "rp": EqualRiskContribution,
    "risk_budget": RiskBudget,
    "rb": RiskBudget,
    "hrp": HierarchicalRiskParity,

    # Tier 4
    "black_litterman": BlackLitterman,
    "bl": BlackLitterman,
}


def get_model(name: str, **kwargs) -> OptimizationModel:
    """Instantiate a model by short name. Used by CLI and API."""
    key = name.lower()
    if key not in MODEL_REGISTRY:
        available = ", ".join(sorted(set(MODEL_REGISTRY)))
        raise ValueError(f"Unknown model: {name!r}. Available: {available}")
    return MODEL_REGISTRY[key](**kwargs)


def list_models() -> list[str]:
    """List unique canonical model names."""
    seen = set()
    unique = []
    for k, cls in MODEL_REGISTRY.items():
        if cls not in seen:
            seen.add(cls)
            unique.append(k)
    return unique


__all__ = [
    "OptimizationModel",
    "OptimizationResult",
    "ConstraintSet",
    "Backend",
    "MODEL_REGISTRY",
    "get_model",
    "list_models",
    # Tier 0
    "EqualWeight", "BuyAndHold", "InverseVolatility",
    # Tier 1
    "Markowitz", "MinimumVariance", "MaximumSharpe", "QuadraticUtility",
    # Tier 2
    "MAD", "TrackingError", "DownsideRisk", "CVaR", "CDaR",
    # Tier 3
    "EqualRiskContribution", "RiskBudget", "HierarchicalRiskParity",
    # Tier 4
    "BlackLitterman",
]
