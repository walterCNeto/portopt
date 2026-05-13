# `portopt` — Status Fase 1

## Entrega desta fase

**Fase 1 — API HTTP completa (Milestone 1)** mais **Frontend MVP esqueleto (Milestone 2 parcial)**.

```
portfolio_proj/
├── 01_fichamento_corpus.md
├── 02_arquitetura.md
├── 03_status_fase0.md
├── 04_design_educacional.md      ← NOVO
├── 05_status_fase1.md            ← NOVO (este arquivo)
├── portopt/                       # biblioteca Python (Fase 0)
│   ├── portopt/
│   │   ├── api/                   ← NOVO (Fase 1)
│   │   │   ├── main.py            ← FastAPI app
│   │   │   ├── settings.py        ← config via env
│   │   │   ├── schemas.py         ← Pydantic v2 com pedagogy first-class
│   │   │   ├── services.py        ← bridge entre API e portopt core
│   │   │   ├── pedagogy.py        ← didática curada por modelo
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       ├── models.py
│   │   │       ├── optimize.py
│   │   │       ├── backtest.py
│   │   │       ├── compare.py
│   │   │       ├── datasets.py
│   │   │       └── data.py
│   │   └── (resto do portopt da Fase 0)
│   └── tests/
│       ├── test_smoke.py          (23 testes Fase 0)
│       ├── test_golden_chagas.py  (12 testes Fase 0)
│       └── test_api.py            ← NOVO (17 testes Fase 1)
└── frontend/                       ← NOVO (Fase 1)
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    ├── README.md
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── lib/
        │   └── api.ts             ← cliente tipado contra a API
        ├── components/
        │   ├── ModelCard.tsx
        │   └── PedagogyBlock.tsx
        ├── pages/
        │   ├── Home.tsx
        │   ├── Catalog.tsx
        │   ├── ModelViewer.tsx
        │   ├── Workshop.tsx
        │   └── Compare.tsx
        └── styles/
            └── globals.css
```

## API HTTP — funcionalidades

✅ **9 endpoints implementados e testados:**

| Endpoint | Método | Função |
|---|---|---|
| `/health` | GET | Liveness + metadata |
| `/api/models` | GET | Catálogo de modelos com pedagogy |
| `/api/models/{name}` | GET | Detalhe didático de um modelo |
| `/api/optimize` | POST | Otimização single-model |
| `/api/backtest` | POST | Backtest rolling com custos |
| `/api/compare` | POST | Comparativo multi-modelo (killer feature) |
| `/api/datasets` | GET | Lista datasets Chagas |
| `/api/datasets/{name}` | GET | Metadata de um dataset |
| `/api/datasets/{name}/prices` | GET | Preços do dataset com subset/downsample |
| `/api/data/prices` | POST | Fetch externo via yfinance/BACEN com cache LRU |

✅ **Pedagogy first-class** — cada modelo tem `PedagogyBlock` curado com:
- `model_name`, `tier`, `one_liner`
- `formula_latex` (KaTeX-ready)
- `chagas_section` (referência ao slide ou notebook)
- `references` (lista de papers fundadores)
- `drawbacks` (limitações conhecidas)
- `when_to_use` (quando aplica bem)

✅ **OpenAPI/Swagger** automático em `/docs` (FastAPI built-in).

✅ **CORS configurado** via env var `PORTOPT_CORS`.

✅ **Validação rigorosa** via Pydantic v2 — bounds, tickers, alpha, tau todos com limites bem definidos.

✅ **Conversão automática** de domínio API ↔ portopt core (services.py).

✅ **Tratamento de erros padronizado** — 400 (validation), 404 (not found), 500 (internal).

## Testes

```
$ pytest
============================ 52 passed in 29.14s =============================

tests/test_smoke.py ............................  (23 testes)
tests/test_golden_chagas.py .................     (12 testes)
tests/test_api.py .................                (17 testes — NOVO)
```

Testes de API cobrem:
- Health/openapi/root endpoints
- Catálogo de modelos com pedagogia
- Otimização com dataset bundled (`ex1`, `mdr`) — sem network
- HRP via API (caminho diferente do solver)
- Validação de inputs (modelo desconhecido = 400, constraint inválida = 422)
- Compare com 3 modelos
- Limite max_compare_models
- Backtest end-to-end
- Datasets endpoints (lista, info, prices com subset)

## Frontend MVP esqueleto

Stack escolhida (confirmada): **FastAPI + React + Vite + TypeScript + Tailwind + Recharts + KaTeX**.

✅ **5 páginas funcionais:**

1. `/` — Landing com hero + 3 pilares + datasets bundled
2. `/catalog` — Catálogo organizado por tier
3. `/models/:name` — Viewer didático com KaTeX
4. `/workshop` — Laboratório single-model (sidebar + main panel)
5. `/compare` — Multi-model side-by-side

✅ **Cliente API tipado** (`src/lib/api.ts`) com tipos espelhando Pydantic.

✅ **Componentes reutilizáveis:**
- `<PedagogyBlock>` — renderiza one_liner + LaTeX + refs + drawbacks
- `<ModelCard>` — card de modelo com tier badge

✅ **Tailwind config** com paleta brand WCN + cores por tier.

✅ **Vite proxy** já configurado para `/api → localhost:8000`.

## Como rodar tudo localmente

```bash
# Terminal 1 — API
cd portopt
pip install -e ".[api,excel_legacy]"
uvicorn portopt.api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev

# Browser
http://localhost:5173   # frontend
http://localhost:8000/docs   # swagger
```

## Deploy planejado

| Camada | Plataforma | Notas |
|---|---|---|
| API | Fly.io (região `gru`) | Padrão do `chassiro-api`. Dockerfile a criar. |
| Frontend | Netlify | Padrão do VCS. Build = `npm run build`, publish = `dist/`. |
| Cache | Upstash Redis | Quando o uso justificar (yfinance é o gargalo). |
| Auth | Firebase Auth | Adicionar antes de ir paga; agora é stateless. |

## Pendências para fechar Fase 1 (Milestone 2 completo)

1. **Implementar todas as telas com qualidade de produção.** O esqueleto está navegável e funcional, mas precisa de:
   - Loading states mais polidos (skeletons)
   - Tratamento de erros visual (toasts)
   - Mobile responsivo (testar em < 768px)
   - Acessibilidade (foco, ARIA labels)

2. **Workspace builder com tickers livres** — hoje só usa datasets bundled. Adicionar fetch via yfinance/BACEN.

3. **Persistência opcional** — salvar uma "sessão" no localStorage para o usuário poder voltar.

4. **Modo "aprendizado" sequencial** — wizard guiando pelos 5 tiers (esperado para v0.2).

5. **CDaR completo** — hoje é stub. Implementação via riskfolio-lib ou linprog próprio.

6. **TrackingError completo** — hoje é stub. É só Markowitz em espaço relativo, ~1 dia.

7. **Dockerfile da API** + Github Actions de CI/CD.

8. **Deploy real** em Fly.io + Netlify, configurar domínio (`portopt.com.br`?).

## Próximas decisões em aberto

1. **Nome do domínio comercial** — `portopt.com.br`? `portopt.wcn.softwares`? Outro?
2. **Modelo de monetização (v2)** — freemium (3 backtests/mês grátis), educacional gratuito + licença comercial, ou só open-source MIT?
3. **Parcerias acadêmicas** — fazer contato direto com o Prof. Chagas (FGV)? Apresentar como ferramenta complementar ao curso dele? Pode virar referência didática brasileira.
4. **Idiomas** — adicionar inglês para alcance internacional, ou ficar PT-BR-first?

## Estatísticas

- **Linhas de Python:** ~6.300 (era 4.762 na Fase 0)
- **Linhas de TypeScript/TSX:** ~1.500
- **Arquivos novos nesta fase:** 27
- **Tests:** 52 (era 35 na Fase 0)
- **Endpoints:** 10
- **Modelos com pedagogy curada:** 14 (faltam tracking_error e cdar)
