# `portopt` — Checklist de publicação

Este guia te leva do estado atual (`portopt_fase1.zip` extraído localmente) até o produto público em:

- **Frontend:** https://waltercneto.github.io/portopt/
- **API:** https://portopt-wcn.fly.dev/

Tempo total estimado: **40-60 minutos** numa primeira execução.

## 0. Pré-requisitos

```bash
# Verificar que tem o necessário
git --version
node --version       # >= 20
python --version     # >= 3.11
fly version          # Fly.io CLI — instalar de fly.io/docs/hands-on/install-flyctl
```

## 1. Inicializar repositório git localmente

```bash
cd portfolio_proj
git init
git branch -M main
git add .
git commit -m "feat: initial public release v0.1.0

Educational portfolio optimization platform based on Prof. Guido Chagas (2024).
- 16 models across 5 tiers (Naive → Robust)
- FastAPI backend with pedagogical metadata per model
- React frontend with KaTeX-rendered formulas
- 3 curated datasets from the Chagas course bundled
- 52 passing tests"
```

## 2. Criar o repositório no GitHub

Opção GUI: criar repo `walterCNeto/portopt` (vazio, sem README/license — já temos).

Opção CLI (com `gh`):
```bash
gh repo create walterCNeto/portopt --public --source=. --remote=origin --description "Plataforma educacional de otimização de portfólios"
```

Push inicial:
```bash
git remote add origin git@github.com:walterCNeto/portopt.git
git push -u origin main
```

## 3. Configurar GitHub Pages

No repositório, em **Settings → Pages**:
- Source: **GitHub Actions**
- (Não escolher branch — o workflow `deploy-frontend.yml` cuida disso)

O primeiro push para `main` vai disparar o workflow automaticamente. Acompanhe em **Actions**.

URL final: `https://waltercneto.github.io/portopt/`

## 4. Configurar deploy da API no Fly.io

### 4a. Criar a app no Fly.io

```bash
fly auth login

# Criar a app SEM deploy ainda
fly launch --name portopt-wcn --region gru --no-deploy
# (Se perguntar para sobrescrever o fly.toml, responda NÃO — o nosso é melhor.)

# Configurar o CORS para apontar para o GH Pages
fly secrets set PORTOPT_CORS="https://waltercneto.github.io"
```

### 4b. Deploy manual (primeira vez)

```bash
fly deploy
```

Aguardar ~5 minutos no primeiro build. Verificar:

```bash
curl https://portopt-wcn.fly.dev/health
# → {"status":"ok","version":"0.1.0","environment":"production","n_models":16,"n_datasets":3}
```

### 4c. Configurar deploy automático via GitHub Actions

No GitHub, em **Settings → Secrets and variables → Actions → New repository secret**:
- Nome: `FLY_API_TOKEN`
- Valor: rodar localmente `fly auth token` e copiar o output

Agora cada push para `main` que tocar em `portopt/**`, `Dockerfile` ou `fly.toml` redeploya automaticamente.

## 5. Validar que tudo está conectado

Abra `https://waltercneto.github.io/portopt/` no browser.

Teste navegando:
- **Catálogo** deve listar 16 modelos com tier coloring
- **Modelo viewer** (clicar em Markowitz) deve mostrar fórmula renderizada via KaTeX
- **Laboratório** deve rodar otimização contra dataset `ex1`
- **Comparar** deve mostrar wealth path de 3+ modelos

Se algo der erro CORS, verificar:
```bash
fly secrets list   # PORTOPT_CORS precisa estar setado
```

## 6. Polimentos pós-deploy (opcionais)

### Domínio próprio

Se quiser `portopt.com.br` ou `portopt.wcn.softwares`:

**Frontend (GH Pages):**
1. Comprar domínio (Registro.br ou GoDaddy)
2. Adicionar arquivo `frontend/public/CNAME` com `portopt.com.br`
3. Configurar DNS:
   - `A` para `185.199.108.153` (e .109, .110, .111)
   - Ou `CNAME` para `waltercneto.github.io`
4. Em GitHub **Settings → Pages → Custom domain**, colocar `portopt.com.br`
5. Habilitar **Enforce HTTPS**

**API (Fly.io):**
```bash
fly certs add api.portopt.com.br
# Atualizar DNS conforme instruções do fly certs show
```

Lembrar de atualizar `VITE_API_BASE` no workflow e `PORTOPT_CORS` no Fly.io.

### Analytics não-invasivo

Adicionar Plausible (open-source, GDPR-friendly) ou similar no `index.html`. Evitar Google Analytics em projeto educacional aberto.

### Status page

Health check público em `/health` já existe. Pode adicionar badge no README:

```markdown
[![API Status](https://img.shields.io/website?url=https%3A%2F%2Fportopt-wcn.fly.dev%2Fhealth)](https://portopt-wcn.fly.dev/health)
```

## 7. Divulgação inicial

Antes de divulgar, considerar:

1. **Outreach ao Prof. Guido Chagas (FGV)** — apresentar o projeto, agradecer pela inspiração do curso. Pode virar referência didática se ele endossar.
2. **Post no LinkedIn / Twitter** explicando o posicionamento educacional.
3. **Post em comunidades brasileiras:**
   - r/farialimabets, r/investimentos (Reddit)
   - Discord/Telegram do EI (Empiricus)
   - Comunidade quantitativa brasileira (existem grupos no LinkedIn)
4. **Conferência / meetup:** apresentar em meetup de Python BR ou em conferência financeira.

## 8. Manutenção contínua

- **Issues e PRs:** triar semanalmente
- **Dependabot:** habilitar para receber PRs de update de dependências
- **CHANGELOG.md:** manter atualizado (criar a partir da v0.2)
- **Releases:** taggear versões: `git tag v0.1.0 && git push --tags`

## Erros comuns

### "API retorna 502 ou timeout"
Fly.io machine pode ter sido stopped. Acessar `/health` uma vez para wake-up. Se quiser sempre on (e pagar pelo idle), no `fly.toml` mudar `min_machines_running = 1`.

### "Frontend mostra rotas 404 ao recarregar uma página interna"
GitHub Pages não suporta client-side routing puro. Solução: adicionar `frontend/public/404.html` igual ao `index.html`. Vou adicionar isso na próxima release se virar problema.

### "CORS error no console do browser"
Verificar:
1. `PORTOPT_CORS` está setado no Fly.io
2. `VITE_API_BASE` no workflow aponta corretamente
3. Não tem barra extra (e.g. `https://portopt-wcn.fly.dev/` vs sem barra)

## Recursos

- [Fly.io docs](https://fly.io/docs/) — pricing, scaling, certs
- [GitHub Pages docs](https://docs.github.com/en/pages)
- [Vite deploy guide](https://vitejs.dev/guide/static-deploy.html#github-pages)
