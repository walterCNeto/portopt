# portopt-frontend

Frontend educacional do `portopt` — React + Vite + TypeScript + Tailwind + Recharts + KaTeX.

Stack: idêntica ao padrão WCN Softwares (SafraRisk, ChassiRO). Branding em PT-BR, posicionamento educacional/acadêmico.

## Páginas

1. **`/`** — landing page, apresenta os 3 pilares (Catálogo, Laboratório, Comparativo) e os 3 datasets educacionais inclusos.
2. **`/catalog`** — catálogo de 16 modelos, organizados em 5 tiers (Naïve → Robust). Cada card mostra nome, descrição one-liner e referência bibliográfica.
3. **`/models/:name`** — viewer didático com fórmula LaTeX (KaTeX), referência ao paper original, drawbacks, drawbacks e quando usar.
4. **`/workshop`** — laboratório single-model: configura modelo + dataset + constraints, executa optimize + backtest, exibe pizza de alocação + wealth path.
5. **`/compare`** — multi-model side-by-side: até 8 modelos, tabela de resumo, wealth paths sobrepostos, métricas comparadas.

## Rodar localmente

```bash
cd frontend
npm install
npm run dev
```

Por padrão proxy redireciona `/api/*` e `/health` para `http://localhost:8000` (onde o uvicorn estará rodando o FastAPI). Para mudar o destino, edite `vite.config.ts` ou defina `VITE_API_BASE`.

Em outro terminal, suba a API:

```bash
cd ../portopt
pip install -e ".[api]"
uvicorn portopt.api.main:app --reload --port 8000
```

Acesse:
- Frontend: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs

## Build de produção

```bash
npm run build
# saída em dist/
```

Deploy: arrastar `dist/` para Netlify, ou conectar repo GitHub e configurar build command `npm run build`.

## Estrutura

```
src/
├── main.tsx              # entry point com BrowserRouter
├── App.tsx               # layout + rotas
├── lib/
│   └── api.ts            # cliente tipado contra a API FastAPI
├── components/
│   ├── ModelCard.tsx     # card de modelo no catálogo
│   └── PedagogyBlock.tsx # bloco didático (LaTeX + drawbacks + refs)
├── pages/
│   ├── Home.tsx
│   ├── Catalog.tsx
│   ├── ModelViewer.tsx
│   ├── Workshop.tsx
│   └── Compare.tsx
└── styles/
    └── globals.css       # Tailwind + classes utilitárias do brand
```

## Próximos passos (após validação do MVP)

- **Modo "aprendizado" sequencial** — wizard que percorre os 5 tiers progressivamente
- **Workspace builder** com tickers livres (yfinance / BACEN), não só datasets curados
- **Exportação** de resultados para LaTeX / Excel / PDF
- **Notebooks pedagógicos** lado-a-lado (Jupyter embed?)
- **Modo escuro**
- **i18n** (atualmente PT-BR hardcoded; inglês para uso internacional)
