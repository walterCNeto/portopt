# portopt

> Plataforma educacional de otimização de portfólios — implementação dos modelos clássicos da literatura, da MV de Markowitz (1952) ao Hierarchical Risk Parity (Lopez de Prado, 2016).

[![Tests](https://github.com/walterCNeto/portopt/actions/workflows/ci.yml/badge.svg)](https://github.com/walterCNeto/portopt/actions/workflows/ci.yml)
[![Deploy](https://github.com/walterCNeto/portopt/actions/workflows/deploy-frontend.yml/badge.svg)](https://github.com/walterCNeto/portopt/actions/workflows/deploy-frontend.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

🌐 **Live:** https://waltercneto.github.io/portopt/
📚 **API docs:** https://portopt-wcn.fly.dev/docs

`portopt` é uma biblioteca Python + REST API + frontend React que implementa **16 modelos de otimização de portfólios** organizados em 5 tiers de complexidade — do equal-weight ingênuo (1/N) ao Hierarchical Risk Parity, passando por Markowitz, MAD, CVaR, ERC, Risk Budgeting e Black-Litterman.

Cada modelo carrega seu próprio **bloco didático** com formulação matemática (LaTeX), referência ao paper original que o introduziu, drawbacks conhecidos e quando aplicá-lo. A interface comparativa permite rodar N modelos no mesmo dataset e analisar lado a lado.

## Tiers

## Modelos disponíveis

| Modelo | Tier | Backend | Status |
|---|---|---|---|
| Equal-Weight, Buy-and-Hold, Inverse Vol | 0 | trivial | ✅ |
| Markowitz, Min Variance, Max Sharpe, Utility | 1 | scipy SLSQP / cvxpy | ✅ |
| MAD | 2 | linprog HiGHS | ✅ |
| Downside Risk | 2 | scipy SLSQP | ✅ |
| CVaR | 2 | linprog HiGHS | ✅ |
| ERC / Risk Parity | 3 | scipy SLSQP (warm-start IV) | ✅ |
| Risk Budget (por grupo) | 3 | scipy SLSQP | ✅ |
| Hierarchical Risk Parity | 3 | scipy hierarchy + IV | ✅ |
| Black-Litterman | 4 | Markowitz com priors Bayesianos | ✅ |
| Tracking Error, CDaR | 2 | — | ⏳ stub |

## Quick start

### Como biblioteca Python

```bash
git clone https://github.com/walterCNeto/portopt.git
cd portopt
pip install -e ".[all]"
```

```python
import portopt as po

prices = po.datasets.subset("ex1", "br_stocks").loc["2018":]

result = po.compare(
    models=["ew", "markowitz", "mad", "erc", "hrp", "cvar"],
    prices=prices,
    constraints=po.ConstraintSet(bounds=(0.0, 0.4)),
    with_backtest=True,
    backtest_config=po.BacktestConfig(
        transaction_costs=po.costs.B3RealisticCost(),
        rebalance="monthly",
    ),
)

print(result.metrics_table())
```

### Como CLI

```bash
portopt list-models
portopt compare --models ew,markowitz,hrp,cvar \
                --tickers PETR4.SA,VALE3.SA,ITUB4.SA,BBDC4.SA \
                --start 2020-01-01 \
                --cost b3 \
                --with-backtest
```

### Como API REST (local)

```bash
pip install -e ".[api]"
uvicorn portopt.api.main:app --reload --port 8000
# Swagger em http://localhost:8000/docs
```

### Como frontend (local)

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

## Datasets bundled

Três datasets curados para exemplos didáticos e exercícios clássicos:

| Nome | Universo | Período |
|---|---|---|
| `ex1` | 24 ações brasileiras + CDI | 2003-12 → 2023-12 |
| `mdr` | 24 commodity futures | 2012-12 → 2023-12 |
| `mcvar` | 24 commodity futures | 2012-12 → 2023-12 |

```python
import portopt as po
prices = po.datasets.load("ex1")
metals = po.datasets.subset("mdr", "metals")
po.datasets.info("ex1")
```

## Arquitetura

┌──────────────────────────────────┐
│  Frontend (React + Vite)         │
│  Hosted at GitHub Pages          │
└────────────────┬─────────────────┘
▼
┌──────────────────────────────────┐
│  REST API (FastAPI + uvicorn)    │
│  Hosted at Fly.io (region: gru)  │
└────────────────┬─────────────────┘
▼
┌──────────────────────────────────┐
│  portopt Python library          │
│  Models · Costs · Backtest       │
│  Estimators · Risk Measures      │
└──────────────────────────────────┘

### Princípios de design

1. **Modelo plugável, engine único.** Todo modelo expõe a mesma interface `fit(returns, constraints) → OptimizationResult`. O `BacktestEngine` consome qualquer modelo da mesma forma.
2. **Look-ahead bias proof.** No backtest, o modelo só recebe a janela `[t - training_window : t]`, nunca dados futuros.
3. **Dois modos de solver.** *Educacional* (scipy SLSQP, fiel à literatura) e *produção* (cvxpy/HiGHS, robusto). Configurável por modelo.
4. **Custos plugáveis.** Do `FlatCost(15bps)` didático até `B3RealisticCost` (emolumentos + liquidação + corretagem) e `TaxAwareCost` (IR brasileiro).
5. **Pedagogia first-class.** Cada modelo no `/api/models/{name}` retorna fórmula LaTeX + paper fundador + drawbacks + when_to_use.

## Referências bibliográficas

A implementação se baseia na literatura clássica e contemporânea de otimização de portfólios:

- Markowitz, H. (1952). Portfolio Selection. *Journal of Finance*, 7(1).
- Tobin, J. (1958). Liquidity Preference as Behavior Towards Risk. *Review of Economic Studies*, 25.
- Sharpe, W. (1966). Mutual Fund Performance. *Journal of Business*, 39.
- Konno, H., Yamazaki, H. (1991). MAD Portfolio Model. *Management Science*, 37.
- Sortino, F., van der Meer, R. (1991). Downside Risk. *Journal of Portfolio Management*, 17(4).
- Black, F., Litterman, R. (1992). Global Portfolio Optimization. *Financial Analysts Journal*, 48(5).
- Rockafellar, R., Uryasev, S. (2000). Optimization of Conditional Value-at-Risk. *Journal of Risk*, 2(3).
- Chekhlov, A., Uryasev, S., Zabarankin, M. (2003). Drawdown Measure in Portfolio Optimization.
- Jorion, P. (2003). Portfolio Optimization with Tracking-Error Constraints. *FAJ*.
- Maillard, S., Roncalli, T., Teiletche, J. (2010). Properties of Equally Weighted Risk Contribution Portfolios. *JPM*.
- Asness, C., Frazzini, A., Pedersen, L. (2012). Leverage Aversion and Risk Parity. *FAJ*.
- Roncalli, T. (2013). Introduction to Risk Parity and Budgeting.
- Lopez de Prado, M. (2016). Building Diversified Portfolios that Outperform Out-of-Sample. *JPM*.

Cada modelo no endpoint `/api/models/{name}` retorna seu próprio bloco de pedagogia com a citação específica do paper original.

## Como contribuir

Pull requests bem-vindos — ver [CONTRIBUTING.md](CONTRIBUTING.md). Áreas prioritárias:

- Implementar CDaR completo (hoje stub)
- Implementar Tracking Error completo
- Universo BR pré-curado (Ibovespa, IBrX, SMLL, FIIs)
- Loaders adicionais (brapi.dev, B3 oficial)
- Modo Pyodide (rodar 100% no browser)
- Internacionalização (EN, ES)

## Licença

MIT — ver [LICENSE](LICENSE).

---

**WCN Softwares** · 2026 · São Paulo, Brasil