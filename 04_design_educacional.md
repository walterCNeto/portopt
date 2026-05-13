# `portopt` — Design Educacional

Posicionamento: **plataforma educacional/acadêmica** baseada no curso *Portfolio Optimization* do Prof. Guido Chagas (2024). Não é ferramenta de trading retail nem dashboard de gestor profissional — é uma sala de aula viva onde o estudante/pesquisador experimenta os modelos com dados reais e compara comportamentos.

## Princípios

1. **Pedagogia como UI de primeira classe.** Cada modelo carrega seu próprio bloco didático: fórmula LaTeX, referência ao slide do Chagas, papers fundadores, drawbacks. Esse bloco é renderizado em todo lugar onde o modelo aparece (não está escondido em "docs" separados).

2. **Progressão por tiers.** O menu replica a estrutura do curso: do mais simples (1/N) ao mais complexo (Black-Litterman). Cada tier tem sua paleta de cor própria e badge no catálogo.

3. **Comparativo é o que vende.** A killer feature é rodar 6 modelos no mesmo dataset e ver lado a lado. Reproduz literalmente o método didático do Chagas (que faz isso o tempo todo no PDF).

4. **Referências bibliográficas explícitas.** Markowitz 1952, Rockafellar-Uryasev 2000, Prado 2016 não viram nota de rodapé — viram cards com link.

5. **Datasets do Chagas como cidadãos de primeira classe.** Não precisa configurar conta nem upload — o usuário entra no laboratório e já tem `ex1`, `mdr` e `mcvar` disponíveis.

## Telas

### 1. `/` Home

- **Hero** com tagline "Otimização de portfólios, do mais simples ao mais complexo"
- 3 pilares clicáveis: Catálogo, Laboratório, Comparativo
- Bloco mostrando os 3 datasets do Chagas inclusos (sem login)
- Footer com atribuição ao curso + licença

### 2. `/catalog` Catálogo

Grid de model cards organizados por tier:

| Tier | Cor brand | Modelos |
|---|---|---|
| **0 · Naïve** | `tier-naive` (cinza) | EW, BH, IV |
| **1 · Allocation** | `tier-allocation` (azul) | Markowitz, MVP, MaxSharpe, Utility |
| **2 · Risk Measures** | `tier-alt_risk` (roxo) | MAD, TE, DR, CVaR, CDaR |
| **3 · Risk Budgeting** | `tier-risk_budget` (verde) | ERC, RB, HRP |
| **4 · Robust** | `tier-robust` (âmbar) | Black-Litterman |
| **Roadmap** | `tier-roadmap` (cinza escuro) | Resampling, Robust strict, Entropy Pooling |

Cada card mostra: tier badge, nome do modelo (Markowitz Mean-Variance), one_liner, risk_measure, seção do Chagas. Hover destaca borda e mostra seta para detalhes.

### 3. `/models/:name` Model Viewer

Página dedicada por modelo:

- Header: badge tier + nome + nomes técnicos (canonical + aliases)
- Bloco didático completo (PedagogyBlock):
  - one_liner em fonte serif itálica
  - Fórmula renderizada via KaTeX em bloco destacado
  - Card "Onde aparece" com seção do Chagas
  - Lista "Quando usar"
  - Lista "Limitações" (em vermelho)
  - Lista "Referências" em font mono
- Call-to-action: "Abrir no laboratório" + "Comparar com Markowitz e EW"

### 4. `/workshop` Laboratório

Sidebar de configuração (280px) + main panel:

**Sidebar:**
- Select de modelo
- Select de dataset (ex1 / mdr / mcvar)
- Select de subset (br_stocks / metais / energia / etc.)
- Date pickers de período
- Slider de peso máximo (0.1 → 1.0)
- Slider de custo em bps (0 → 50)
- Botão "Executar"

**Main panel após execução:**
- Card de alocação: pie chart + tabela de métricas in-sample (risco, E[R] anualizado, convergência, tempo)
- Card de backtest: 4 stats em cards (Sharpe, Vol a.a., Max DD, Total return) + line chart de cumulative wealth

### 5. `/compare` Comparativo

A killer feature:

**Topo:**
- Grid de pílulas de modelos clicáveis (toggle) — até 8 selecionados
- Selects de dataset + subset
- Checkbox "Incluir backtest mensal (15 bps)"
- Botão "Comparar"

**Resultados:**
- **Tabela resumo:** uma linha por modelo com risco, E[R], medida, n° ativos, peso máx
- **Wealth path:** line chart com N curvas sobrepostas (uma por modelo)
- **Métricas comparadas:** tabela com métricas (rows) × modelos (cols), permitindo identificar visualmente "qual modelo tem maior Sharpe?", "qual tem menor MDD?"

## Branding visual

- **Fonte serif** (Lora) para títulos e elementos didáticos (one_liner, refs)
- **Fonte sans** (Inter) para UI/dados
- **Fonte mono** (JetBrains Mono) para tickers, código, valores numéricos
- **Cores brand:** azul institucional `#0F4C81` (primary), laranja acadêmico `#E07B00` (accent)
- **Cores tier:** paleta consistente do catálogo até detalhe do modelo
- Microinteração: hover em cards eleva sombra e desliza ícone de seta

## Stack técnica

| Camada | Tech |
|---|---|
| Backend | FastAPI + uvicorn (Fly.io, região `gru`) |
| Frontend | Vite + React 18 + TypeScript |
| UI/Style | Tailwind CSS + classes brand (model-card, ref-card, tier-badge) |
| Gráficos | Recharts |
| Matemática | KaTeX (CDN, sem build) |
| Estado | useState/useEffect — sem Redux. Simplicidade > arquitetura. |
| HTTP | Axios com tipos TypeScript espelhando Pydantic |
| Roteamento | react-router-dom |
| Auth | Firebase Auth (a adicionar quando virar paga) |

## O que está fora do escopo MVP

- Login / multi-tenant
- Persistência de portfólios
- Stripe / billing
- Modo escuro
- i18n (PT-BR hardcoded por enquanto)
- Mobile-first responsivo (responsivo OK, mas otimizado para desktop)
- Integração com brokers
- Dados intraday

## Próximas iterações (v0.2+)

1. **Modo aprendizado sequencial** — wizard que faz o aluno percorrer Tier 0 → Tier 4, com checkpoints conceituais
2. **Workspace builder** com tickers livres (não só datasets curados)
3. **Exportação para LaTeX / Excel / PDF** — útil para teses, dissertações
4. **Tooltips contextuais** explicando termos (Sharpe ratio, drawdown, etc.) ao passar o mouse
5. **Modo "side-by-side notebook"** — célula de Jupyter incorporada com o código equivalente

## Métricas de sucesso (educacional)

- Tempo médio até primeiro "Executar" no laboratório
- Taxa de uso do `/compare` (indica que o usuário entendeu a proposta)
- Modelos mais visitados em `/models/:name` (sugere lacunas no Chagas que merecem destaque)
- Datasets mais usados (validar valor do bundle Chagas)
- Compartilhamento de URLs de modelos específicos (e.g. `/models/hrp` em aulas)
