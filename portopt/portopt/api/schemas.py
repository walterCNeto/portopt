"""Pydantic schemas for the portopt REST API.

Design decisions for the educational positioning:

1. Every model response carries a `pedagogy` field with formula (LaTeX),
   references (Chagas slide, original papers), and an interpretation hint.

2. Every request validates upfront against the configured limits
   (max_tickers, max_backtest_years, etc.) — fail fast with clear errors.

3. Dates are accepted as ISO strings; serialized back as YYYY-MM-DD.

4. All numeric fields use bounded constraints reflecting Chagas' guardrails
   (e.g. alpha in [0.001, 0.5] for CVaR; tau in [0.01, 0.99] for BL).
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ===========================================================================
# Common types
# ===========================================================================

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        json_schema_extra={"namespace": "portopt"},
    )


DataSource = Literal["yfinance", "bacen", "dataset"]
ModelTier = Literal[
    "naive", "allocation", "alt_risk", "risk_budget", "robust", "roadmap"
]
RiskMeasure = Literal[
    "vol", "variance", "mad", "downside_risk", "var", "cvar",
    "cdar", "tracking_error",
]


# ===========================================================================
# Constraint set
# ===========================================================================

class GroupSpec(BaseSchema):
    """Asset group with optional bounds and risk budget."""
    name: str = Field(min_length=1)
    assets: list[str] = Field(min_length=1)
    min_weight: Optional[float] = Field(None, ge=-2.0, le=2.0)
    max_weight: Optional[float] = Field(None, ge=-2.0, le=2.0)
    risk_budget: Optional[float] = Field(None, ge=0.0, le=1.0)


class ConstraintsSchema(BaseSchema):
    """Portfolio constraints, mirrored on portopt.ConstraintSet."""
    bounds: tuple[float, float] = Field((0.0, 1.0))
    sum_to: Optional[float] = Field(1.0)
    target_return: Optional[float] = Field(None, description="Per-period log return")
    target_vol: Optional[float] = Field(None, ge=0.0, description="Per-period volatility")
    target_risk: Optional[float] = Field(None, ge=0.0)
    risk_aversion: Optional[float] = Field(None, ge=0.0, le=100.0)
    groups: list[GroupSpec] = Field(default_factory=list)
    benchmark_weights: Optional[dict[str, float]] = Field(
        None, description="Required by tracking_error model"
    )

    @field_validator("bounds")
    @classmethod
    def validate_bounds(cls, v):
        if v[0] > v[1]:
            raise ValueError(f"bounds[0]={v[0]} must be <= bounds[1]={v[1]}")
        return v


# ===========================================================================
# Cost spec
# ===========================================================================

class CostSpec(BaseSchema):
    """Cost model specification.

    Examples
    --------
    {"kind": "flat", "rate_bps": 15}                        # 15 bps flat (Chagas baseline)
    {"kind": "b3_realistic"}                                 # B3 emolumentos + liquidação
    {"kind": "b3_realistic", "futures": true}                # B3 futures
    {"kind": "offshore"}                                     # ~50 bps + FX
    {"kind": "tax_aware", "equity_rate": 0.15}               # BR IR on RV
    {"kind": "zero"}                                         # theoretical
    """
    kind: Literal["flat", "tiered", "b3_realistic", "offshore", "tax_aware", "zero"] = "flat"
    rate_bps: Optional[float] = Field(None, ge=0.0, le=500.0, description="For flat cost")
    futures: bool = False
    equity_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    fii_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    bond_rate: Optional[float] = Field(None, ge=0.0, le=1.0)


# ===========================================================================
# Data specification — how to load prices
# ===========================================================================

class DataSpec(BaseSchema):
    """How to load price data for an optimization.

    Options:
    - source="yfinance": fetch from Yahoo (BR via .SA suffix). `tickers` required.
    - source="bacen":    fetch from BACEN SGS (CDI, IPCA, USD_PTAX, ...). `tickers` required.
    - source="dataset":  use a curated dataset (Chagas 2024 included).
                         `dataset` required; `tickers` may be empty to take all columns.
    """
    source: DataSource = "yfinance"
    tickers: list[str] = Field(default_factory=list, max_length=40)
    start: date
    end: Optional[date] = None
    dataset: Optional[str] = Field(None, description="When source='dataset'")
    subset: Optional[str] = Field(None, description="Subset of the dataset")
    log_returns_frequency: Literal["1D", "5D", "ME", "QE"] = "1D"

    @field_validator("tickers")
    @classmethod
    def at_least_one_when_external(cls, v, info):
        # Only enforce non-empty tickers for external sources
        source = info.data.get("source", "yfinance")
        if source != "dataset" and len(v) == 0:
            raise ValueError(f"`tickers` is required when source='{source}'")
        return v


# ===========================================================================
# Black-Litterman views
# ===========================================================================

class BLViewSpec(BaseSchema):
    """A Black-Litterman view (absolute or relative).

    Examples:
    - {"assets": ["SPY"], "weights": [1.0], "expected": 0.10}          # absolute
    - {"assets": ["SPY","QQQ"], "weights": [1.0,-1.0], "expected": 0.02}  # SPY beats QQQ by 2%
    """
    assets: list[str] = Field(min_length=1)
    weights: list[float] = Field(min_length=1)
    expected: float = Field(description="Expected (excess) return of the linear combination")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class BlackLittermanSpec(BaseSchema):
    market_weights: dict[str, float] = Field(description="ω_M per ticker")
    delta: float = Field(default=2.5, ge=0.0, le=10.0, description="Market price of risk")
    tau: float = Field(default=0.05, ge=0.01, le=0.99)
    views: list[BLViewSpec] = Field(min_length=1)


# ===========================================================================
# Model parameters
# ===========================================================================

class ModelParams(BaseSchema):
    """Model-specific hyperparameters."""
    # CVaR / CDaR
    alpha: Optional[float] = Field(None, ge=0.001, le=0.5)
    n_scenarios: Optional[int] = Field(None, ge=0, le=100_000)
    # IV / ERC
    vol_estimator: Optional[Literal["sample", "ewma"]] = None
    ewma_halflife: Optional[int] = Field(None, ge=5, le=500)
    # HRP
    linkage_method: Optional[Literal["single", "complete", "average", "ward"]] = None
    # Utility
    risk_aversion: Optional[float] = Field(None, ge=0.0, le=100.0)
    # Risk Budget
    approach: Optional[Literal["1", "2"]] = None
    # Downside Risk
    mar: Optional[float] = None
    # MaxSharpe
    risk_free_rate: Optional[float] = Field(None, description="Per-period log RF")
    # Tracking error
    target_te: Optional[float] = Field(None, ge=0.0)
    # Black-Litterman (separate spec)
    black_litterman: Optional[BlackLittermanSpec] = None
    # Backend
    backend: Optional[Literal["scipy", "cvxpy", "linprog"]] = None


# ===========================================================================
# Pedagogy block — first-class educational metadata
# ===========================================================================

class PedagogyBlock(BaseSchema):
    """Educational metadata attached to every model response."""
    model_name: str
    tier: ModelTier
    one_liner: str
    formula_latex: str
    chagas_section: str = Field(
        description="Where this is covered in Chagas (2024) PDF / notebook"
    )
    references: list[str] = Field(default_factory=list)
    drawbacks: list[str] = Field(default_factory=list)
    when_to_use: list[str] = Field(default_factory=list)


# ===========================================================================
# Model info — for the menu and documentation
# ===========================================================================

class ModelInfo(BaseSchema):
    """Model menu entry, with pedagogy."""
    name: str
    aliases: list[str] = Field(default_factory=list)
    tier: ModelTier
    risk_measure: RiskMeasure
    requires_returns_history: bool
    supports_short: bool
    pedagogy: PedagogyBlock


# ===========================================================================
# Optimize endpoint
# ===========================================================================

class OptimizeRequest(BaseSchema):
    """Single-model optimization on the full sample."""
    model: str = Field(min_length=1, description="Model name (see /models)")
    data: DataSpec
    constraints: ConstraintsSchema = Field(default_factory=ConstraintsSchema)
    params: ModelParams = Field(default_factory=ModelParams)


class OptimizationResponse(BaseSchema):
    model: str
    weights: dict[str, float]
    expected_return: Optional[float]
    risk: float
    risk_measure: RiskMeasure
    converged: bool
    diagnostics: dict = Field(default_factory=dict)
    pedagogy: Optional[PedagogyBlock] = None
    elapsed_ms: float = 0.0


# ===========================================================================
# Backtest endpoint
# ===========================================================================

class BacktestConfigSchema(BaseSchema):
    training_window: int = Field(252, ge=20, le=1500)
    rebalance: Literal["monthly", "weekly", "quarterly"] = "monthly"
    cost: CostSpec = Field(default_factory=CostSpec)
    initial_weights: Literal["equal", "zero", "first_alloc"] = "first_alloc"


class BacktestRequest(BaseSchema):
    model: str
    data: DataSpec
    constraints: ConstraintsSchema = Field(default_factory=ConstraintsSchema)
    params: ModelParams = Field(default_factory=ModelParams)
    config: BacktestConfigSchema = Field(default_factory=BacktestConfigSchema)


class BacktestPointSchema(BaseSchema):
    date: date
    log_return: float
    cumulative_wealth: float
    cost_paid: float


class BacktestResponse(BaseSchema):
    model: str
    points: list[BacktestPointSchema] = Field(
        description="Time series. Dense for short backtests, downsampled for long ones."
    )
    rebalance_dates: list[date]
    metrics: dict[str, float]
    total_cost_paid: float
    weights_at_end: dict[str, float]
    pedagogy: Optional[PedagogyBlock] = None
    elapsed_ms: float = 0.0


# ===========================================================================
# Compare endpoint (the killer feature)
# ===========================================================================

class CompareModelSpec(BaseSchema):
    model: str
    params: ModelParams = Field(default_factory=ModelParams)


class CompareRequest(BaseSchema):
    models: list[CompareModelSpec] = Field(min_length=2, max_length=8)
    data: DataSpec
    constraints: ConstraintsSchema = Field(default_factory=ConstraintsSchema)
    with_backtest: bool = False
    backtest_config: Optional[BacktestConfigSchema] = None


class CompareResponse(BaseSchema):
    optimizations: dict[str, OptimizationResponse]
    backtests: Optional[dict[str, BacktestResponse]] = None
    summary_table: list[dict]  # rows for easy table rendering
    weights_table: dict[str, dict[str, float]]  # asset -> {model -> weight}
    elapsed_ms: float = 0.0


# ===========================================================================
# Dataset endpoints
# ===========================================================================

class DatasetInfo(BaseSchema):
    name: str
    description: str
    period: str
    exercise: str
    subsets: dict[str, str]
    n_assets: int
    n_dates: int


class DatasetPrices(BaseSchema):
    name: str
    subset: Optional[str] = None
    columns: list[str]
    dates: list[date]
    # Prices returned as flat array of arrays (more compact than dict-of-dicts)
    values: list[list[Optional[float]]]


# ===========================================================================
# Health / meta
# ===========================================================================

class HealthResponse(BaseSchema):
    status: Literal["ok"] = "ok"
    version: str
    environment: str
    n_models: int
    n_datasets: int
