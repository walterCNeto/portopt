# portopt

> Plataforma educacional de otimização de portfólios, baseada no curso *Portfolio Optimization* do **Prof. Guido Chagas (2024)**.

[![Tests](https://github.com/walterCNeto/portopt/actions/workflows/ci.yml/badge.svg)](https://github.com/walterCNeto/portopt/actions/workflows/ci.yml)
[![Deploy](https://github.com/walterCNeto/portopt/actions/workflows/deploy-frontend.yml/badge.svg)](https://github.com/walterCNeto/portopt/actions/workflows/deploy-frontend.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

🌐 **Live:** https://waltercneto.github.io/portopt/
📚 **API docs:** https://portopt-wcn.fly.dev/docs

`portopt` é uma biblioteca Python + REST API + frontend React que implementa **16 modelos de otimização de portfólios** organizados em 5 tiers de complexidade — do equal-weight ingênuo (1/N) ao Hierarchical Risk Parity de López de Prado, passando por Markowitz, MAD, CVaR, ERC, Risk Budgeting e Black-Litterman.

Cada modelo carrega seu próprio **bloco didático** com fórmula em LaTeX, referência ao slide correspondente do Chagas, papers fundadores, drawbacks conhecidos e quando usar. A interface comparativa permite rodar N modelos no mesmo dataset e analisar lado a lado — exatamente o método didático usado em sala de aula.

## Sumário

- [Em três tier](#em-três-tier)
- [Modelos disponíveis](#modelos-disponíveis)
- [Quick start](#quick-start)
- [Datasets do Chagas inclusos](#datasets-do-chagas-inclusos)
- [Arquitetura](#arquitetura)
- [Como contribuir](#como-contribuir)
- [Reconhecimentos](#reconhecimentos)

## Em três tier

```
Tier 0 · Naïve            EW · BH · IV
Tier 1 · Allocation       Markowitz · MVP · MaxSharpe · Quadratic Utility
Tier 2 · Risk Measures    MAD · TE · Downside Risk · CVaR · CDaR
Tier 3 · Risk Budgeting   ERC · Risk Budget (por grupo) · HRP
Tier 4 · Robust           Black-Litterman (com Bayes-Stein e Ledoit-Wolf)
```

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

# Use um dos datasets do Chagas (zero config)
prices = po.datasets.subset("ex1", "br_stocks").loc["2018":]

# Compare 6 modelos no mesmo dataset
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

## Datasets do Chagas inclusos

| Nome | Universo | Período | Exercício |
|---|---|---|---|
| `ex1` | 24 ações brasileiras + CDI | 2003-12 → 2023-12 | nb1 — MV vs EW backtest |
| `mdr` | 24 commodity futures | 2012-12 → 2023-12 | nb2 — Mean-Downside-Risk |
| `mcvar` | 24 commodity futures (mesmo universo) | 2012-12 → 2023-12 | nb2 — Mean-CVaR |

Os datasets vêm distribuídos com o pacote (versionados em `portopt/data_files/chagas_2024/`) — não é preciso fazer upload nem cadastro.

```python
import portopt as po
prices = po.datasets.load("ex1")
metals = po.datasets.subset("mdr", "metals")
po.datasets.info("ex1")  # metadata estruturado
```

## Arquitetura

```
┌──────────────────────────────────┐
│  Frontend (React + Vite)         │
│  Hosted at GitHub Pages           │
│  → fetch /api → API Fly.io        │
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│  REST API (FastAPI + uvicorn)    │
│  Hosted at Fly.io (region: gru)   │
│  /api/optimize, /api/backtest,    │
│  /api/compare, /api/datasets, ... │
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│  portopt Python library          │
│  Models · Cost Models · Backtest │
│  Estimators · Risk Measures      │
│  Datasets (Chagas 2024)          │
└──────────────────────────────────┘
```

### Princípios de design

1. **Modelo plugável, engine único.** Todo modelo expõe a mesma interface `fit(returns, constraints) → OptimizationResult`. O BacktestEngine consome qualquer modelo da mesma forma.

2. **Look-ahead bias proof.** No backtest, o modelo só recebe a janela `[t - training_window : t]`, nunca dados futuros.

3. **Dois modos de solver.** *Educacional* (scipy SLSQP, reproduz linha-a-linha o Chagas) e *produção* (cvxpy/HiGHS, robusto). Configurável por modelo.

4. **Custos como componente plugável.** Do `FlatCost(15bps)` didático até `B3RealisticCost` (emolumentos + liquidação + corretagem) e `TaxAwareCost` (IR brasileiro).

5. **Pedagogia first-class.** Cada modelo no `/api/models/{name}` retorna não só a referência técnica, mas formula LaTeX + paper fundador + drawbacks + when_to_use.

## Como contribuir

Pull requests são muito bem-vindos! Ver [CONTRIBUTING.md](CONTRIBUTING.md).

Áreas onde contribuições têm alto valor:

- **Implementar CDaR completo** (hoje é stub)
- **Implementar Tracking Error completo** (~1 dia, é MV em espaço relativo)
- **Modelos Tier 5 (roadmap):** Resampling (Michaud), Robust strict (Goldfarb-Iyengar), Entropy Pooling (Meucci)
- **Universo BR pré-curado** (Ibovespa, IBrX, SMLL, FIIs)
- **Loaders adicionais**: brapi.dev, B3 oficial, Refinitiv
- **Internacionalização do frontend** (PT-BR → EN, ES)
- **Modo Pyodide** — rodar 100% no browser (sem API)

Antes de mandar PR, rode:

```bash
cd portopt
pytest                        # 52 testes, ~30s
ruff check portopt            # lint
```

## Reconhecimentos

A estrutura conceitual, exposição matemática e exemplos didáticos deste repositório (incluindo os 3 datasets em `portopt/data_files/chagas_2024/`) são baseados no curso **Portfolio Optimization** do Prof. Guido Chagas (2024). Erros de implementação são exclusivamente dos autores.

Bibliotecas que carregam a base matemática: [numpy](https://numpy.org), [scipy](https://scipy.org), [pandas](https://pandas.pydata.org), [scikit-learn](https://scikit-learn.org), [cvxpy](https://www.cvxpy.org), [FastAPI](https://fastapi.tiangolo.com), [Vite](https://vitejs.dev), [React](https://react.dev), [Tailwind](https://tailwindcss.com), [Recharts](https://recharts.org), [KaTeX](https://katex.org).

## Licença

MIT — ver [LICENSE](LICENSE).

---

**WCN Softwares** · 2026 · São Paulo, Brasil
