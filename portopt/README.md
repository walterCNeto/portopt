# portopt

**Portfolio Optimization Toolkit** — WCN Softwares

Software construído com base na literatura clássica de otimização de portfólios, oferecendo um *menu* unificado de modelos de otimização de portfólios, da MV clássica de Markowitz até técnicas modernas (HRP, CVaR, Black-Litterman).

## Por que este software existe

Os notebooks didáticos clássicos implementam cada modelo separadamente, com loops de backtest duplicados. O `portopt` factura o que é comum (loading de dados, drift de pesos, custos de transação, métricas) e deixa o usuário escolher *só o modelo*. Mesma rigor matemático, sem ter que copiar-colar 200 linhas de boilerplate por experimento.

## Filosofia

- **Modelo plugável, engine único.** Cada modelo é uma classe que implementa `fit(returns) → weights`. O backtest engine consome qualquer modelo da mesma forma.
- **Look-ahead bias proof por design.** O engine só expõe a janela de treino ao modelo.
- **Dois modos de solver.** `educational` (scipy SLSQP, fiel à formulação clássica) e `production` (cvxpy ou HiGHS, robusto).
- **Custos como componente plugável.** De flat bps (didático) até modelo realista com IR brasileiro.
- **Backend BR-first.** Universo nativo de B3 + BACEN SGS, com offshore via yfinance.

## Instalação

```bash
# Pacote básico
pip install -e .

# Com solvers convexos (cvxpy)
pip install -e ".[convex]"

# Tudo (dev + api + brasil + convex + riskfolio)
pip install -e ".[all]"
```

## Uso mínimo

```python
import portopt as po

# 1. Carrega preços
prices = po.data.load_prices(
    tickers=["PETR4.SA", "VALE3.SA", "ITUB4.SA", "SPY", "QQQ"],
    start="2020-01-01",
    end="2024-12-31",
)

# 2. Calcula log-returns
returns = po.returns.to_log_returns(prices)

# 3. Escolhe um modelo
model = po.models.Markowitz()  # ou MAD, CVaR, HRP, BlackLitterman, ...

# 4. Define constraints
constraints = po.ConstraintSet(bounds=(0.0, 0.40), target_vol=0.12)

# 5. Fit
result = model.fit(returns, constraints)
print(result.weights)

# 6. Backtest (opcional)
bt = po.BacktestEngine(config=po.BacktestConfig(rebalance="monthly"))
bt_result = bt.run(prices, model, constraints)
print(bt_result.metrics)
```

## Comparativo entre modelos

```python
result = po.compare(
    models=["markowitz", "hrp", "cvar", "black_litterman"],
    prices=prices,
    constraints=constraints,
)
result.plot_frontiers()
```

## CLI

```bash
portopt optimize --model hrp --tickers PETR4.SA,VALE3.SA,SPY --start 2020-01-01
portopt backtest --model markowitz --config configs/conservative.yaml
portopt compare --models markowitz,hrp,cvar --tickers <...>
```

## Estrutura

```
portopt/
├── data.py             # PriceLoader, Universe (yfinance, brapi, BACEN, Excel)
├── returns.py          # log/simple, conversões, resample
├── estimators.py       # μ e Σ: Sample, EWMA, JamesStein, BayesStein, LedoitWolf
├── risk_measures.py    # vol, MAD, DR, VaR, CVaR, CDaR, MRC, RC
├── costs.py            # FlatCost, B3RealisticCost, TaxAwareCost
├── backtest.py         # BacktestEngine, BacktestConfig, BacktestResult
├── metrics.py          # Sharpe, Sortino, Calmar, drawdown
├── viz.py              # plots (EF, allocation area, risk contribs)
├── cli.py              # CLI (Click)
├── api/                # FastAPI (módulo opcional)
└── models/
    ├── base.py           # OptimizationModel, ConstraintSet, OptimizationResult
    ├── naive.py          # EqualWeight, BuyAndHold, InverseVolatility
    ├── markowitz.py      # MV, MVP, MaxSharpe, MaxReturn
    ├── utility.py        # Quadratic Utility
    ├── mad.py            # Mean-Absolute Deviation (com linprog)
    ├── tracking.py       # Tracking Error
    ├── downside.py       # Mean-Downside Risk
    ├── cvar.py           # Mean-CVaR (linprog)
    ├── cdar.py           # Mean-CDaR (linprog)
    ├── erc.py            # Equal Risk Contribution (Risk Parity)
    ├── risk_budget.py    # Risk Budgeting por grupo
    ├── hrp.py            # Hierarchical Risk Parity
    └── black_litterman.py
```

## Validação contra os notebooks

A pasta `tests/golden/` reproduz os exercícios clássicos da literatura. Sempre que possível, os outputs do `portopt` são comparados *bit-a-bit* aos outputs originais — garantia de que a refatoração não introduziu regressões matemáticas.

## Licença

MIT (em discussão; pode evoluir para AGPL ou comercial conforme estratégia de produto).

## Reconhecimentos

Toda a estrutura conceitual e os exemplos didáticos são baseados no curso *Portfolio Optimization* do **classical portfolio optimization literature**. Erros de implementação são exclusivamente do autor.
 
