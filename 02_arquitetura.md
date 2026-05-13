# `portopt` — Arquitetura do Software

**Objetivo.** Transformar o conteúdo didático do Prof. Guido Chagas (deck + 4 notebooks) em um software produtizado da WCN Softwares, no qual o usuário escolhe em um menu o modelo de otimização, fornece dados de preços (BR + offshore) e recebe alocação ótima + backtest + métricas comparativas.

**Princípio condutor.** Nos 4 notebooks, Chagas repete o mesmo backtest com pequenas variações na etapa de otimização. **O backtest é commodity. O modelo é o produto.** A arquitetura precisa refletir isso: engine genérico + modelos plugáveis.

---

## Mapeamento corpus → notebooks → módulos

| Capítulo PDF | Notebook | Modelos | Módulo `portopt` |
|---|---|---|---|
| §2 MV + Utility | `nb1` | MV, Utility quadrática, BH, EW | `models/markowitz.py`, `models/utility.py`, `models/naive.py` |
| §3 Alt. Risk Measures | `nb2` | MAD, TE, Downside Risk, CVaR | `models/mad.py`, `models/tracking.py`, `models/downside.py`, `models/cvar.py` |
| §3 (extensão PDF) | — | CDaR | `models/cdar.py` |
| §4 Risk Budgeting | `nb3` | IV, ERC, RB, HRP | `models/inverse_vol.py`, `models/erc.py`, `models/risk_budget.py`, `models/hrp.py` |
| §5 Robust | `nb4` | Shrinkage estimators, Black-Litterman | `estimators.py`, `models/black_litterman.py` |
| (Roadmap v2) | — | Michaud Resampling, Robust strict, Entropy Pooling | `models/resampling.py`, `models/robust.py`, `models/entropy.py` |

---

## Camadas

### 1. Dados (`portopt.data`)

- `PriceLoader` abstrato. Implementações: `YFinanceLoader`, `BrapiLoader`, `BACENLoader` (SGS para CDI/IPCA/Selic), `ExcelLoader` (para reproduzir os `.xlsx` do Chagas).
- `Universe(tickers, loader, **kwargs)` → DataFrame de preços alinhado e limpo (ffill com warning).
- Cache local em parquet + Redis opcional.

### 2. Retornos (`portopt.returns`)

- `to_log_returns(prices, freq='1d')` → log-returns alinhados, drop NaN.
- `to_simple_returns(log)`, `compound(log)`, `expm1`/`log1p` helpers.
- `resample(returns, freq)` — daily → weekly (5d) → monthly (21d) com aviso de autocorrelação.

### 3. Estimadores (`portopt.estimators`)

Cobertura completa dos métodos do Chagas:

```python
class MeanEstimator:           # ABC
    def fit(self, returns: pd.DataFrame) -> np.ndarray: ...

class SampleMean(MeanEstimator)
class EWMAMean(MeanEstimator)           # halflife configurável
class JamesStein(MeanEstimator)
class BayesStein(MeanEstimator)         # Jorion (1986)
class CAPMImpliedMean(MeanEstimator)    # Π = δΣω_M (para Black-Litterman)

class CovEstimator:            # ABC
    def fit(self, returns: pd.DataFrame) -> np.ndarray: ...

class SampleCov(CovEstimator)
class EWMACov(CovEstimator)             # halflife=63 default (3m)
class LedoitWolfCC(CovEstimator)        # constant correlation (Chagas)
class LedoitWolfShrinkage(CovEstimator) # sklearn wrapper
class DenoisedCov(CovEstimator)         # RMT, Prado (2020) — v2
```

### 4. Medidas de risco (`portopt.risk_measures`)

Funções puras: recebem pesos + retornos (ou covs), devolvem escalar. Usadas como objetivo de otimização **e** para reporting:

```python
def vol(weights, cov): ...
def mad(weights, returns): ...
def downside_risk(weights, returns, mar=0): ...
def var(weights, returns, alpha=0.05): ...
def cvar(weights, returns, alpha=0.05): ...
def cdar(weights, returns, alpha=0.05): ...
def tracking_error(weights, benchmark_weights, cov): ...

def marginal_risk_contrib(weights, cov): ...   # MRC
def risk_contrib(weights, cov): ...            # RC = w * MRC
def risk_contrib_pct(weights, cov): ...        # RC / vol_P
```

### 5. Modelos de otimização (`portopt.models`)

**Interface única.** Todo modelo implementa:

```python
class OptimizationModel(Protocol):
    name: str
    requires_returns_history: bool       # MAD/CVaR/CDaR precisam, MV não
    supports_constraints: list[str]      # ["box", "sum_to_one", "vol_target", "group"]

    def fit(
        self,
        returns: pd.DataFrame,
        constraints: ConstraintSet,
        **kwargs,
    ) -> OptimizationResult: ...

@dataclass
class OptimizationResult:
    weights: pd.Series                   # nome ↔ peso
    expected_return: float | None
    risk: float                          # na unidade do modelo
    risk_measure: str                    # "vol", "mad", "cvar", ...
    converged: bool
    diagnostics: dict                    # iterations, status_message, condition_number
    raw: Any                             # objeto cru do solver
```

**Constraints como objeto.** Inspirado no que Chagas constrói à mão em cada célula:

```python
@dataclass
class ConstraintSet:
    bounds: tuple[float, float] | list[tuple] = (0.0, 1.0)
    sum_to: float | None = 1.0
    target_return: float | None = None      # >=
    target_vol: float | None = None         # <=
    group_bounds: dict[str, tuple] = {}     # {"Energy": (0.2, 0.5), ...}
    group_risk_budgets: dict[str, float] = {}
    asset_groups: dict[str, list[str]] = {} # {"Energy": ["WTI", "Brent", ...]}
    no_short: bool = True
    max_leverage: float | None = None
```

**Backends de solver.** Cada modelo pode usar:

- `scipy.optimize.minimize(SLSQP)` — modo educacional (igual ao Chagas)
- `scipy.optimize.linprog(HiGHS)` — modo produção para problemas linearizados (MAD, CVaR, CDaR)
- `cvxpy` — modo produção para problemas convexos genéricos
- `riskfolio-lib` — wrapper para validação cruzada

Configurável via `OptimizationModel(backend="cvxpy")`.

### 6. Backtest engine (`portopt.backtest`)

Engine **único** que aceita qualquer `OptimizationModel`. Replica fielmente o loop do Chagas mas com responsabilidades separadas:

```python
@dataclass
class BacktestConfig:
    training_window: int = 252            # 1y diário
    rebalance: str | Callable = "monthly" # ou "weekly", "quarterly", custom
    transaction_costs: CostModel          # ver §7
    initial_weights: str = "equal"        # "equal" | "zero" | "previous"
    leverage_allowed: bool = False
    look_ahead_safe: bool = True          # garantia hard

class BacktestEngine:
    def run(
        self,
        prices: pd.DataFrame,
        model: OptimizationModel,
        constraints: ConstraintSet,
        config: BacktestConfig,
    ) -> BacktestResult: ...

@dataclass
class BacktestResult:
    weights_history: pd.DataFrame         # T x N
    log_returns: pd.Series                # T
    cumulative_returns: pd.Series         # T
    risk_contribs: pd.DataFrame           # T x N (ex-ante, na janela)
    realized_risk: pd.Series              # T (ex-post rolling)
    rebalance_dates: list[pd.Timestamp]
    transaction_costs_paid: pd.Series
    metrics: PerformanceMetrics
```

### 7. Custos (`portopt.costs`)

Camada que o usuário pediu explicitamente. Vai além do `trns_costs = 0.0015` flat do Chagas:

```python
class CostModel(Protocol):
    def cost(self, current_weights, new_weights, prices, ...) -> float: ...

class FlatCost(CostModel)               # bps lineares (Chagas baseline)
class TieredCost(CostModel)             # por tamanho de trade
class B3RealisticCost(CostModel)        # emolumentos + liquidação + corretagem
class OffshoreCost(CostModel)           # bps + custos de FX (PTAX)
class TaxAwareCost(CostModel)           # ganho de capital BR (15% RV, IR RF)
class CompositeCost(CostModel)          # soma vários custos
```

### 8. Métricas (`portopt.metrics`)

Sharpe, Sortino, Calmar, max drawdown, downside deviation, Omega, ulcer index, etc. Reusa funções de `risk_measures`. Equivalente do `quantstats` que o Chagas menciona com ressalvas.

### 9. Visualização (`portopt.viz`)

Funções puras matplotlib (servem para notebook) e helpers Plotly (servem para frontend). Mesmos gráficos do Chagas: fronteira eficiente, EF com tangência, allocation area, risk contributions area, drawdown, dendrograma do HRP.

### 10. API (`portopt.api`)

FastAPI expondo os modelos. Endpoint principal:

```
POST /optimize
{
  "model": "hrp",                   # nome do modelo do menu
  "tickers": ["PETR4.SA", "VALE3.SA", "SPY", "QQQ"],
  "start": "2020-01-01",
  "end": "2025-01-01",
  "constraints": { ... },
  "config": { "backend": "cvxpy" },
  "include_backtest": true,
  "backtest_config": { "rebalance": "monthly", "transaction_costs": {...} }
}
→ { "weights": {...}, "metrics": {...}, "backtest": {...} }
```

Endpoint comparativo (o diferencial do produto):

```
POST /compare
{
  "models": ["markowitz", "hrp", "cvar", "black_litterman"],
  "tickers": [...], ...
}
→ { "markowitz": {...}, "hrp": {...}, ... }
```

Sub-endpoints utilitários: `/data/prices`, `/data/risk_free`, `/estimators/preview`.

---

## Menu de modelos (UX)

A ordem do menu replica a progressão didática do Chagas, etiquetada por complexidade:

| Tier | Modelo | Custo computacional | Inputs adicionais |
|---|---|---|---|
| **Tier 0** — Naïve | Equal-Weight (EW) | trivial | nenhum |
| | Buy-and-Hold (BH) | trivial | data inicial |
| | Inverse Volatility (IV) | O(N) | janela vol |
| **Tier 1** — Allocation-based | Markowitz MVP | QP O(N³) | μ, Σ |
| | Markowitz EF | QP por ponto | μ, Σ, target |
| | Utility (quadratic) | QP O(N³) | μ, Σ, λ |
| | Tangency Portfolio | QP O(N³) | μ, Σ, R_f |
| **Tier 2** — Risk Measures | MAD | LP O((N+2T)) | retornos T×N |
| | Tracking Error | QP | benchmark |
| | Downside Risk | QP custom | MAR |
| | CVaR | LP O((N+1+S)) | cenários S |
| | CDaR | LP path-dep | cenários T |
| **Tier 3** — Risk Budgeting | Equal Risk Contribution (ERC) | NLP convexo | Σ |
| | Risk Budgeting (RB) por grupo | NLP | Σ, grupos, budgets |
| | Hierarchical Risk Parity (HRP) | O(N² + N log N) | Σ, método clustering |
| **Tier 4** — Robust | Shrinkage MV (BS + LW) | QP O(N³) + LW O(N²T) | retornos T×N |
| | Black-Litterman | linear algebra | Π, P, Q, Ω, τ |
| **Tier 5** (roadmap) | Michaud Resampling | QP × M | M ≈ 500 |
| | Robust Opt (box / ellipsoidal) | SOCP/QCQP | uncertainty set |
| | Entropy Pooling | otimização entrópica | views complexas |

A UI deve indicar qual nível de input cada modelo exige (μ, Σ, retornos brutos, benchmark, views) — pois muda quanto trabalho o usuário tem antes de rodar.

---

## Stack tecnológica final (resumo)

**Núcleo Python (lib `portopt`):**
- `numpy`, `scipy`, `pandas` — core
- `cvxpy` (opcional) — solvers convexos genéricos
- `riskfolio-lib` (opcional) — referência cruzada
- `scikit-learn` — LedoitWolf nativo
- `yfinance`, `python-bcb` — dados
- `pyarrow` — cache parquet

**API/SaaS:**
- `fastapi`, `uvicorn`, `pydantic` v2 — backend (padrão SafraRisk/ChassiRO)
- Frontend: a definir (escolha sua pendente)
- Persistência: Postgres no Fly.io ou Firestore (depende do plano de billing)
- Cache: Upstash Redis (Yfinance é lento; cache de séries é vitalícia)
- Deploy: Fly.io região `gru` (mesmo padrão do `chassiro-api`)

**Testes:**
- `pytest` + `hypothesis` para invariantes (pesos somam 1, vol_P ≥ 0, ERC tem RC ≈ const)
- **Golden tests** contra os XLSX do Chagas (quando você subir): reproduzir exatamente os outputs dos notebooks valida a corretude.

---

## Mapa de implementação por fase

**Fase 0 — Esqueleto (esta entrega).** Estrutura de pastas, interfaces vazias, 2-3 modelos implementados como exemplo do padrão. CLI mínima rodando.

**Fase 1 — MVP funcional (1-2 semanas).** Todos os Tier 0 + Tier 1 + Tier 2 (MAD, CVaR). Backtest engine funcionando. Testes golden contra notebooks. CLI completa.

**Fase 2 — Risk budgeting completo (1 semana).** IV, ERC, RB, HRP. Visualizações de risk contributions.

**Fase 3 — Robust (1 semana).** Shrinkage estimators + Black-Litterman.

**Fase 4 — API + frontend.** FastAPI exposing models, deploy Fly.io. Frontend conforme escolha.

**Fase 5 — Roadmap.** Resampling, Robust strict, Entropy Pooling, Dimensionality Reduction (PCA, Factor Models), Multi-objetivo, Intertemporal.

---

## Decisões de design já tomadas

1. **Modelo plugável, engine único.** Confirmado pela análise dos notebooks: a única coisa que varia é a função-objetivo + constraints, e isso é exatamente uma interface.

2. **Dois modos de solver:** *educacional* (scipy, comparável linha-a-linha ao Chagas) e *produção* (cvxpy/HiGHS, robusto e rápido). Útil para didática + produto.

3. **Custos como componente plugável, não constante.** Reflete pedido explícito do usuário.

4. **Look-ahead bias proof por design.** O `BacktestEngine` recebe `prices` e expõe ao modelo apenas a janela `[t - training_window : t]` — nunca dados futuros.

5. **Π implied returns calculados via Σ × ω_M, não de retornos históricos** (consistente com BL de Chagas) — mas com fallback de uso histórico para usuários sem `ω_M` claro.

6. **HRP usa Recursive Bisection com Inverse Variance** (fiel ao Prado 2016 e ao notebook), não risk parity puro dentro de cada cluster.

7. **Identificação de modelos por string** (`"hrp"`, `"black_litterman"`, ...) — facilita CLI, API REST e UI.
