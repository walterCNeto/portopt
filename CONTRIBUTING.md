# Como contribuir para o portopt

Obrigado pelo interesse! `portopt` é um projeto educacional aberto e contribuições são bem-vindas.

## Code of conduct

Seja gentil. Respeite divergências técnicas. Discussões sobre matemática financeira são bem-vindas — debates pessoais não.

## Setup local

```bash
git clone https://github.com/walterCNeto/portopt.git
cd portopt

# Backend
cd portopt
pip install -e ".[all]"
pytest                      # deve passar tudo

# Frontend
cd ../frontend
npm install
npm run dev
```

## Como fazer um PR

1. **Fork** o repo no GitHub
2. Crie uma branch descritiva: `git checkout -b feat/cdar-implementation` ou `fix/erc-convergence`
3. Faça commits pequenos e descritivos. Em PT-BR ou EN, tanto faz.
4. Rode testes localmente: `pytest`
5. Rode o linter: `ruff check portopt`
6. **Abra o PR** descrevendo: o problema, a solução, e referências (papers) se for matemática.

## O que vale um PR de alta qualidade

### Para novos modelos
- Implementar `OptimizationModel` com `fit() → OptimizationResult`
- Registrar em `MODEL_REGISTRY` com nome canônico + aliases
- Adicionar `PedagogyBlock` em `portopt/api/pedagogy.py` com:
  - `formula_latex` em forma compilável
  - Citação do paper original (autor, ano, periódico)
  - Referência à seção do Chagas PDF se aplicável
  - Lista honesta de `drawbacks`
- Adicionar smoke test em `tests/test_smoke.py`
- Bonus: golden test contra dataset Chagas em `tests/test_golden_chagas.py`

### Para novos custos
- Implementar `CostModel` protocol em `portopt/costs.py`
- Documentar fontes para os bps usados (e.g. tabela B3 oficial vigente)
- Registrar em `COST_MODELS`

### Para frontend
- Manter TS strict
- Componentes pequenos e reutilizáveis
- Sem dependências pesadas novas sem discussão prévia (preferimos manter bundle leve)

### Para a API
- Schemas Pydantic em `schemas.py`
- Rotas em `routes/` por domínio
- Lógica em `services.py`, não na rota
- Tests em `tests/test_api.py` usando TestClient

## Princípios técnicos

1. **Reproducibilidade.** Se um teste falha às vezes, ele está errado. Use `random_state` explícito.
2. **Look-ahead-bias proof.** Em backtests, o modelo só pode ver o passado. O `BacktestEngine` garante isso por design — não burle.
3. **Custos são plugáveis.** Não enfie custos em código de modelo; passe via `CostModel` para o `BacktestEngine`.
4. **Pedagogia first-class.** Nada é "documentação separada que faz fora do código". Tudo aparece via `PedagogyBlock` retornado pela API.
5. **Datasets curados** ficam em `portopt/data_files/`. Para adicionar um, abra uma issue antes — precisamos discutir licenciamento.

## Roadmap de contribuições prioritárias

| Prioridade | Tarefa | Esforço estimado |
|---|---|---|
| 🔴 Alta | Implementar CDaR completo (hoje é stub) | 2-3 dias |
| 🔴 Alta | Implementar TrackingError completo | 1 dia |
| 🟡 Média | Universo BR pré-curado (Ibovespa, IBrX, SMLL, FIIs) | 2 dias |
| 🟡 Média | Loader brapi.dev | 1 dia |
| 🟡 Média | Modo Pyodide (rodar 100% no browser) | 1 semana |
| 🟢 Boa | Modelos Tier 5: Resampling, Robust strict, Entropy Pooling | 1 semana cada |
| 🟢 Boa | i18n frontend (EN, ES) | 2 dias |

## Onde discutir antes de codar

- **Issues no GitHub** para bugs e feature requests
- **Discussions** para questões conceituais ("o que é melhor: Markowitz com Bayes-Stein ou com Ledoit-Wolf shrinkage?")
- Para mudanças grandes (refactor de engine, adicionar dependência pesada), abra issue antes

## Reconhecimento

Toda contribuição aceita aparece na lista de contributors. Para mudanças significativas, também adicionamos crédito no CHANGELOG e nas notas de release.

---

WCN Softwares · contato em via Issues do GitHub
