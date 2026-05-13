# `portopt` — Status da Fase 0

## O que esta entrega contém

Implementação completa da **Fase 0** prevista no documento de arquitetura (`02_arquitetura.md`): biblioteca Python `portopt` com infra de loading, estimadores, medidas de risco, modelos plugáveis, engine de backtest, modelos de custo plugáveis, comparador, CLI e testes.

```
portopt/
├── pyproject.toml                          # build + deps (com extras [convex] [api] [brasil])
├── README.md                                # documentação de uso
├── portopt/
│   ├── __init__.py                          # API pública (po.compare, po.BacktestEngine, ...)
│   ├── data.py                              # YFinance, Excel, BACEN, brapi (stub) loaders
│   ├── returns.py                           # log↔simple, resample, annualize, cumulative wealth
│   ├── estimators.py                        # Sample, EWMA, JamesStein, BayesStein, LedoitWolf
│   ├── risk_measures.py                     # vol, MAD, DR, VaR, CVaR, CDaR, MRC, RC
│   ├── costs.py                             # Flat, Tiered, B3Realistic, Offshore, TaxAware, Composite
│   ├── backtest.py                          # BacktestEngine genérico (replica loop dos 4 NBs)
│   ├── metrics.py                           # Sharpe, Sortino, Calmar, Omega, MDD, Ulcer, VaR/CVaR
│   ├── compare.py                           # compare(): roda múltiplos modelos lado-a-lado
│   ├── cli.py                               # CLI: list-models, optimize, backtest, compare
│   ├── viz.py                               # plots matplotlib (EF, allocation, RC, dendrogram)
│   └── models/                              # MENU DE MODELOS
│       ├── __init__.py                      # MODEL_REGISTRY (16 entradas + 8 aliases)
│       ├── base.py                          # OptimizationModel, ConstraintSet, OptimizationResult
│       ├── naive.py                         # EqualWeight, BuyAndHold, InverseVolatility       [IMPL]
│       ├── markowitz.py                     # Markowitz, MinVar, MaxSharpe (scipy + cvxpy)     [IMPL]
│       ├── utility.py                       # QuadraticUtility                                  [IMPL]
│       ├── mad.py                           # MAD (linprog HiGHS, conforme Chagas)             [IMPL]
│       ├── downside.py                      # DownsideRisk                                      [IMPL]
│       ├── cvar.py                          # CVaR (linprog HiGHS)                             [IMPL]
│       ├── erc.py                           # EqualRiskContribution                             [IMPL]
│       ├── risk_budget.py                   # RiskBudget (2 abordagens)                         [IMPL]
│       ├── hrp.py                           # HierarchicalRiskParity (3 stages)                [IMPL]
│       ├── black_litterman.py               # BlackLitterman (direct + Woodbury)               [IMPL]
│       ├── tracking.py                      # TrackingError                                    [STUB]
│       └── cdar.py                          # CDaR                                             [STUB]
├── tests/
│   └── test_smoke.py                        # 23 testes, todos passando
└── notebooks/
    └── 00_quick_tour.ipynb                  # tour reproduzindo espírito dos NBs do Chagas
```

## O que funciona end-to-end (validado por testes)

✅ **16 modelos registrados** com 8 aliases (`MODEL_REGISTRY`)
✅ **10 modelos implementados completamente** com fit() funcional
✅ **Backtest engine genérico** que aceita qualquer modelo via interface única
✅ **6 modelos de custo plugáveis** (Flat, Tiered, B3Realistic, Offshore, TaxAware, Composite)
✅ **Função `compare()`** rodando múltiplos modelos lado-a-lado com tabelas de pesos e métricas
✅ **CLI funcional** (`portopt list-models`, `portopt optimize`, `portopt backtest`, `portopt compare`)
✅ **Suite de 23 testes** rodando em < 2s, incluindo invariantes matemáticas (Euler em ERC, MVP ≤ EW, IV proporcional a 1/σ)

## Mapeamento corpus → notebooks → módulos (entregue)

| Capítulo Chagas | Notebook | Modelo `portopt` | Status |
|---|---|---|---|
| §2 MV+Utility | nb1 | `Markowitz`, `MinimumVariance`, `MaximumSharpe`, `QuadraticUtility`, `EqualWeight`, `BuyAndHold` | ✅ |
| §3 MAD | nb2 | `MAD` (linprog HiGHS) | ✅ |
| §3 TE | nb2 | `TrackingError` | ⏳ stub |
| §3 DR | nb2 | `DownsideRisk` | ✅ |
| §3 CVaR | nb2 | `CVaR` (linprog HiGHS) | ✅ |
| §3 CDaR | (PDF only) | `CDaR` | ⏳ stub (sugere riskfolio) |
| §4 IV | nb3 | `InverseVolatility` (sample/EWMA) | ✅ |
| §4 ERC | nb3 | `EqualRiskContribution` (warm-start IV) | ✅ |
| §4 RB | nb3 | `RiskBudget` (abordagens 1 e 2) | ✅ |
| §4 HRP | nb3 | `HierarchicalRiskParity` (HC + QD + RB completos) | ✅ |
| §5 Shrinkage | nb4 | `BayesStein`, `JamesStein`, `LedoitWolfCC` em `estimators.py` | ✅ |
| §5 BL | nb4 | `BlackLitterman` (direct + Woodbury cross-check) | ✅ |

## Componente de custos (pedido explícito do usuário)

Stack completo de modelos plugáveis em `costs.py`:

- **`FlatCost(rate)`** — 15bps/2bps/10bps (baseline Chagas)
- **`TieredCost(tiers)`** — desconto por tamanho de trade
- **`B3RealisticCost`** — emolumentos + liquidação + corretagem + ISS, com flag `futures`
- **`OffshoreCost`** — bps + SEC fee + spread FX
- **`TaxAwareCost`** — IR brasileiro (15% RV swing, 20% day trade, 20% FII, RF regressivo)
- **`CompositeCost`** — soma de componentes (B3 + IR, offshore + FX, etc.)
- **`ZeroCost`** — para teóricos / unit tests

Cada um implementa o mesmo Protocol `CostModel.cost(w_current, w_new, prices?, nav?, dt?) -> float`, plugável no `BacktestEngine` via `BacktestConfig(transaction_costs=...)`.

## Padrão arquitetural confirmado

O esqueleto dos 4 notebooks de Chagas, analisado linha a linha, mostrou-se idêntico: a única coisa que varia é a função-objetivo da otimização. Isso é exatamente o que `OptimizationModel.fit()` abstrai. O backtest engine processa qualquer modelo sem mudança.

Resultado: o que no notebook nb1 são ~80 linhas de loop (cell 100), no `portopt` é:

```python
result = po.BacktestEngine().run(prices, po.models.Markowitz(), constraints)
```

## Próximos passos sugeridos (decisões pendentes)

1. **XLSX do Chagas (`Ex1.xlsx`, `CVaR Example.xlsx`, `RB Example 3.xlsx`)** — quando você subir, gero **golden tests** que reproduzem bit-a-bit os resultados dos exercícios. É a validação definitiva de correção.
2. **Stack frontend (Fase 4)** — pergunta pendente. FastAPI + React (padrão SafraRisk/ChassiRO) é o caminho natural; alternativas: FastAPI + HTML estático (VCS) ou Streamlit (prototipagem). Eu sugiro **FastAPI + React** dado seu padrão atual.
3. **Tier 5 (roadmap)** — Resampling/Michaud, Robust strict (Goldfarb-Iyengar), Entropy Pooling, PCA/Factor Models. Implemento quando você quiser priorizar.
4. **CDaR e TrackingError completos** — stubs hoje. CDaR via `riskfolio-lib` é trivial; TE é só MV em espaço relativo.
5. **Persistência** — Postgres no Fly.io ou Firestore para histórico de otimizações.
6. **Cache** — Upstash Redis para séries do yfinance/BACEN (latência alta hoje).

## Para começar a usar agora

```bash
cd portopt
pip install -e ".[all]"
portopt list-models
portopt compare --models ew,markowitz,hrp,cvar --tickers SPY,QQQ,TLT,GLD --start 2020-01-01 --with-backtest
```

Ou em Python:

```python
import portopt as po

prices = po.data.load_prices(["PETR4.SA", "VALE3.SA", "SPY", "TLT"], start="2020-01-01")
log_rets = po.returns.to_log_returns(prices)

# Compara o menu inteiro
comparison = po.compare(
    models=["ew", "markowitz", "mad", "hrp", "cvar"],
    prices=prices,
    constraints=po.ConstraintSet(bounds=(0.0, 0.4)),
    with_backtest=True,
    backtest_config=po.BacktestConfig(
        transaction_costs=po.costs.B3RealisticCost(),
        rebalance="monthly",
    ),
)
print(comparison.metrics_table())
```
