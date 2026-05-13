# Fichamento — *Portfolio Optimization* (Prof. Guido Chagas, 2024)

**Documento-fonte:** `Portfolio_Optimization.pdf`, 233 slides, exportado de PowerPoint, datado de 18/06/2024.
**Status:** corpus principal do projeto **Portfolio Optimizer / WCN Softwares**.
**Estrutura entregue:** 5 seções (do sumário original, faltam ainda no PDF as seções de *Dimensionality Reduction* — PCA, Factor Models — e *Further Topics* — Multi-Objective, Intertemporal, Libraries; provavelmente são partes II e III do curso).

---

## 1. Introdução à otimização de portfólios

Chagas posiciona otimização como **busca pela melhor solução em algum sentido**, e — o ponto explícito que ele repete — *não existe abordagem universal*. As escolhas são trade-offs entre complexidade, tractabilidade e velocidade.

A taxonomia que ele apresenta divide as técnicas em três famílias macro: **determinísticas** (LP, NLP, MILP, programação dinâmica, otimização convexa, QP, otimização combinatória), **machine learning** (supervisionado e não-supervisionado) e **estocásticas/metaheurísticas** (algoritmos gulosos, hill-climbing, PSO, Ant Colony, GA, GP, *simulated annealing*). Ortogonais a essas, três classes especialmente relevantes em finanças: **robusta, multi-objetivo e intertemporal**.

Da Teoria da Complexidade, ele lembra que problemas não-lineares e não-convexos tipicamente caem em **NP-Hard** — o que sustenta a recomendação prática de *linearizar sempre que possível* (que aparece com força nas seções de MAD, CVaR e CDaR).

A frase-síntese: *"garbage in, garbage out"*. Quanto mais restrições adicionadas, mais difícil convergência confiável → soluções de canto e *poor convergence* viram regra.

---

## 2. Mean-Variance e Utility (Markowitz)

### 2.1 Setup

Universo de N instrumentos arriscados, T log-retornos por instrumento. Matrizes $R$, $\bar R = E[R]$, $\Sigma = \mathrm{Cov}(R)$, $P = \mathrm{Corr}(R)$, e $\Sigma = \mathrm{diag}(\sigma) \cdot P \cdot \mathrm{diag}(\sigma)$. Pesos $\omega$ com $\omega'\mathbf 1 = 1$.

Pressupostos clássicos: sem limites de empréstimo, retornos log-normais, sem custos/impostos, sem assimetria de informação, sem arbitragem, investidores racionais, mercados líquidos.

### 2.2 Três formulações equivalentes

$$\max_\omega \bar R_P \;\;\text{s.t.}\;\; \Sigma_P \le \Sigma_{tgt}, \quad \min_\omega \Sigma_P \;\;\text{s.t.}\;\; \bar R_P \ge \mu_{tgt}, \quad \max_\omega \left[\bar R_P - \tfrac{1}{2}A\Sigma_P\right]$$

Observação prática importante: usa-se **variância** (não volatilidade) na função-objetivo porque o resultado é uma forma quadrática, mais tratável. A solução analítica de Markowitz aparece no PDF via Lagrangiano duplo (constraint de retorno + constraint de soma), gerando o sistema $\binom{\lambda_1}{\lambda_2} = M^{-1}\binom{\mu_{tgt}}{1}$ com $M$ contendo $\bar R'\Sigma^{-1}\bar R$, $\bar R'\Sigma^{-1}\mathbf 1$, $\mathbf 1'\Sigma^{-1}\mathbf 1$.

### 2.3 Casos didáticos

O Chagas constrói progressivamente:
- **Caso 1:** 2 ativos, sem short. Mostra benefício da correlação ($\rho < 1$) e introduz MVP via $\partial \Sigma_P / \partial \omega_1 = 0$ analítico, depois via `scipy.optimize.fminbound` (Brent).
- **Caso 2:** N=5, sem short. Introduz `scipy.optimize.minimize` para restrições lineares/quadráticas.
- **Caso 3:** N=5 com short (-0,25 a 1,25). Já com **dados reais**: Ibovespa, S&P 500, US10, Brent, Corn (169 retornos mensais 2009–2023). Aviso sobre dados não-ajustados (futuros sem roll, dividendos não ajustados) e o problema de *carrying costs*.
- **Caso 4:** com ativo livre de risco. Três abordagens: (1) $\omega_0 = 1 - \omega'\mathbf 1$ no constraint, (2) ativo RF dentro de $\omega$/$\bar R$/$\Sigma$, (3) portfólio de mercado + equação simples $w_P = (\mu_{tgt} - \bar R_0)/(\bar R_M - \bar R_0)$.

### 2.4 Tangency, Tobin, CML

Portfolio de mercado: $\omega_M = \dfrac{\Sigma^{-1}(\bar R - \mathbf 1 R_0)}{\mathbf 1'\Sigma^{-1}(\bar R - \mathbf 1 R_0)}$. Teorema da separação de Tobin (1958): todo portfólio eficiente é combinação convexa do RF + portfolio de mercado. CML: $\bar R_P = R_0 + \sigma_P (\bar R_M - R_0)/\sigma_M$, sendo o segundo termo o *market price of risk*.

### 2.5 Utility Theory (von Neumann-Morgenstern)

Função utilidade estritamente crescente, $C^2$, satisfazendo transitividade/continuidade/completude. Risco: $\lambda = -U''(\cdot)/U'(\cdot)$ (coeficiente de Arrow-Pratt). Funções típicas:
- Quadrática: $U(W) = W - 0.5\lambda W^2$
- Exponencial: $U(W) = 1 - e^{-\lambda W}$
- Power: $U(W) = W^{1-\lambda}$
- Logarítmica: $U(W) = \ln W$

A quadrática é a "ponte natural" com MV: depende apenas de $\bar R$ e $\Sigma$ e aproxima outras utilidades via Taylor de 2ª ordem em torno de $E[\bar R_P]$.

Conceitos auxiliares: **Certainty Equivalent** ($U(CE) = E[U(\cdot)]$) e **Risk Premium** ($RP = E[\cdot] - CE$). Acena para **Prospect Theory** (Kahneman 1979) como alternativa à EUT — Tobin não vale sempre, ativos não são precificados igualmente por todos os investidores racionais.

### 2.6 Comparativo backtest: MV vs Buy&Hold vs Equal-Weight

Sample real: 6 ações US, 15 anos diários, janela rolling de 5y para estimação, rebalanceamento mensal, custos de 15bps. **MV não vence** consistentemente. Razões que ele aponta:
1. Janela de 5y é longa demais para momentum (que opera melhor em ≤1y); EWMA ou DCC ajudariam.
2. MV concentra risco (50/50 equity/bonds **não é** diversificado em risco).
3. Retornos esperados baseados em médias históricas raramente são bons estimadores ex-ante.

Cita `quantstats` (Ran Aroussi) para métricas de performance, com ressalva: *sempre revisar código de terceiros*.

### 2.7 Críticas ao MV (decisivas para o produto)

1. **Volatilidade é medida de dispersão, não de risco.** Só funciona em distribuições simétricas sem cauda pesada. Duas distribuições com mesmo $\mu$ e $\sigma$ podem ter probabilidades de perda completamente diferentes.
2. **Diárias e intradiárias têm excesso de curtose e às vezes skew alto** (FX, crédito). Modelar com gaussiana subestima cauda.
3. **Não considera incerteza dos estimadores.** Pequenas variações em $\bar R$, $\sigma$, $\rho$ → mudanças enormes nas alocações (o "error maximizer" do Michaud).
4. **Curse of dimensionality:** N parâmetros + N(N-1)/2 covariâncias. Sample size T frequentemente insuficiente.
5. **Matriz mal-condicionada** quando ativos são altamente correlacionados; $\Sigma^{-1}$ amplifica erros.
6. **Soluções não-únicas.** Mesma fronteira eficiente pode ser atingida por diferentes alocações → custos de transação descontrolados se não incluídos na função-objetivo (Lobo-Fazel-Boyd 2005).

**Suggested readings:** Best (2010, Matlab), Brugière (2010, Python), Zivot (forthcoming, R).

---

## 3. Optimization using Alternative Risk Measures

### 3.1 Risk measures coerentes (Artzner-Delbaen-Heath, 1999)

Quatro axiomas: subaditividade, homogeneidade positiva, monotonicidade, invariância translacional. Subaditividade + homogeneidade podem ser substituídas pela condição mais fraca de **convexidade** (Föllmer-Schied 2002).

Distinção-chave: **dispersion measure** (volatilidade, MAD, TE) ≠ **risk measure** (DR, CVaR, CDaR). Dispersão só vale como proxy de risco se a distribuição for simétrica.

### 3.2 MAD — Mean-Absolute Deviation (Konno-Yamazaki 1991)

$$\mathrm{MAD} = \frac{1}{T-1}\sum_{t=1}^T |r_{t,P} - \mu_P|$$

Conhecido também como modelo L1 (MV é L2). Vantagens: não depende da matriz de covariâncias e a otimização pode ser **linearizada** (variáveis auxiliares $y_t, z_t \ge 0$, com $y_t - z_t = \sum_i (r_{t,i} - \mu_i)\omega_i$, minimizando $\sum (y_t + z_t)$). Alocações mais parsimoniosas (positions pequenas zeram) → menor *rebalancing overhead* em portfólios grandes.

Aviso prático: SLSQP falha em portfólios grandes; usar `scipy.optimize.linprog` (HiGHS) é dramaticamente mais rápido.

### 3.3 Tracking Error (TE)

$$\mathrm{TE} = \sqrt{(\omega_P - \omega_B)'\Sigma(\omega_P - \omega_B)}$$

Classificação de portfólios: **passivo** (TE baixo, busca rastrear), **ativo** (TE controlado, busca alpha), **enhanced** (smart-beta). TE também pode ser definido como desvio do erro $\varepsilon$ em $R_P = \alpha + \beta R_B + \varepsilon$.

Exemplo concreto: portfólio ativo contra benchmark 60/40 (ACWI + GBMI) com permissão de NDX e TE alvo de 1%. Avisos:
- TE baixo não implica risco absoluto baixo (cripto rastreada perfeitamente: TE≈0, vol altíssima).
- Combinar TE com vol absoluta na restrição evita derrapagens.
- ETFs reais usam **MILP/MINLP** para acomodar custos, liquidez, roll de futuros (libs: APOPT, GEKKO, Pyomo).

### 3.4 Downside Risk (Sortino-Meer 1991)

$$\mathrm{DR} = \sqrt{\frac{1}{T-1}\sum_{t=1}^T \min(r_{t,P} - \mathrm{MAR}, 0)^2}$$

MAR ajustável (zero, $\mu$, taxa risk-free). Quando MAR = $\mu$, DR vira semi-desvio (sqrt do LPM₂). É um *risk measure* de fato, não dispersão. Formulação Mean-DR análoga à Markowitz, trocando $\Sigma_P$ por DR².

### 3.5 VaR e CVaR (Rockafellar-Uryasev 2000, 2002)

$$\mathrm{VaR}_{1-\alpha} \approx F^{-1}_{R_P}(\alpha), \qquad \mathrm{CVaR}_{1-\alpha} = E[R_P \mid R_P < F^{-1}_{R_P}(\alpha)] \approx \frac{1}{\alpha}\int_0^\alpha \mathrm{VaR}_{1-s}\,ds$$

**VaR não é coerente** (falha subaditividade), CVaR sim. Métodos: paramétrico, simulação histórica, simulação estocástica.

A função auxiliar de Rockafellar-Uryasev:
$$F_\alpha(\omega, z) = z + \frac{1}{\alpha}\int (-R_P(\omega, r) - z)^+ p(s)\,ds$$
com a propriedade fundamental $\min_\omega \mathrm{CVaR}_\alpha(\omega) = \min_{\omega, z} F_\alpha(\omega, z)$. Discretização com M cenários e variáveis auxiliares $u_m \ge 0$, $u_m \ge -R_P - z$ transforma a otimização em **LP** — novamente, `linprog`, não SLSQP.

**Drawbacks do CVaR:** tende a portfólios concentrados e soluções de canto; depende de muitas amostras na cauda (recomendação: $S \ge 10^6$ simulações); pode não ser finito; o exemplo do PDF com 10.000 simulações gaussianas multivariadas subestima a cauda (sub-amostragem + distribuição errada).

### 3.6 CDaR — Conditional Drawdown-at-Risk (Chekhlov-Uryasev-Zabarankin 2003)

Aplicado sobre **drawdowns** (cauda da distribuição dos drawdowns), não dos retornos. Path-dependent, baseado em retornos não-compostos para preservar propriedades matemáticas:

$$f(\omega, \tau) = \max_{1 \le k \le \tau} \sum_i \sum_{s=1}^k r_{i,s}\omega_i - \sum_i\sum_{s=1}^\tau r_{i,s}\omega_i$$

Linearização análoga à do CVaR, com restrições adicionais $u_m \ge u_{m-1}$ (monotonicidade do drawdown acumulado). Penaliza fortemente instrumentos com drawdowns frequentes; portfólios MCDaR diferem **muito** de MCVaR mesmo no mesmo universo.

### 3.7 Síntese da Seção 3 (palavras do Chagas)

Combinar diferentes medidas → mais balanço, porque impõe diversificação em várias dimensões de risco. Linearizar sempre que possível. Otimização ex-ante e ex-post devem ser comparáveis — se não são, algo está errado. Soluções ótimas raramente são únicas.

---

## 4. Optimization based on Risk Budgeting

### 4.1 Por que sair de allocation-based para risk-based

Allocation-based depende de retornos esperados (ruído) → instabilidade. Risk-based ignora retornos esperados (ou os usa só como prior) e foca em **contribuições de risco**.

### 4.2 Inverse Volatility (IV)

$\omega_i \propto 1/\sigma_i$. Recomenda **EWMA** para estimar $\sigma_i$ (dá peso a eventos recentes). Não usa correlações — caso particular degenerado do RP com $\Sigma$ diagonal (também chamado *Naïve ERC*).

### 4.3 Marginal Risk Contribution e Euler

Decomposição via teorema de Euler (volatilidade é homogênea de grau 1):

$$\mathrm{MRC}_i = \frac{\partial \sigma_P}{\partial \omega_i} = \frac{(\Sigma\omega)_i}{\sqrt{\omega'\Sigma\omega}}, \quad \mathrm{RC}_i = \omega_i \cdot \mathrm{MRC}_i, \quad \sigma_P = \sum_i \mathrm{RC}_i$$

### 4.4 ERC (Equal Risk Contribution) / Risk Parity

Maillard-Roncalli-Teiletche (2010). Procura $\omega$ tal que $\mathrm{RC}_i = \sigma_P / N$ para todo i. Formulação:

$$\min_\omega \sum_i \left(\omega_i \frac{(\Sigma\omega)_i}{\sigma_{P,tgt}^2} - \frac{1}{N}\right)^2 \;\;\text{s.t.}\;\; \omega'\mathbf 1 = 1,\;\omega_i \ge 0,\;\omega'\Sigma\omega = \sigma_{P,tgt}^2$$

Problema clássico: quando target vol é alta vis-à-vis o universo (ex.: tentar 10% vol com S&P 500 + US 2y + US 10y, onde a média rondaria 2–4%), alavancagem em ativos de baixa vol explode. Volatilidade não penaliza tail risk → drawdowns catastróficos (referência implícita aos colapsos de Risk Parity em 2020/2022).

Mitigação: pesos limitados + complementar com CVaR (se a multivariada for simulada com qualidade). Para SLSQP convergir bem, usar IV como starting point ou `basinhopping`.

### 4.5 Risk Budgeting (RB)

Generalização do ERC: contribuições alvo distintas por grupo. No PDF, exemplo com commodities agrupadas (Metais 20%, Energia 30%, Agricultura 30%, Livestock 20%). Duas formulações:

**Abordagem 1** (restrição dura): mantém objetivo ERC, adiciona restrição $\sum_{j\in \Omega_k} \omega_j (\Sigma\omega)_j / (\omega'\Sigma\omega) = \mathrm{RB}_{tgt,k}$ por grupo.

**Abordagem 2** (objetivo agregado): $\min_\omega \sum_k \left(\sum_{i\in\Omega_k}\omega_i \mathrm{RC}_i - \mathrm{RB}_{tgt,k}\right)^2$.

Diferem nos pesos individuais; abordagem 2 não força ERC dentro de cada grupo.

Frame geral de Feng-Palomar (2015): $\min U(\omega) = R(\omega) + \lambda F(\omega)$ com $R$ = objetivo de risco, $F$ = preferência (ex.: $-\mu'\omega$ para tiltar retornos). Calibrar $\lambda$ é tricky (alto não-convexo).

### 4.6 HRP — Hierarchical Risk Parity (Lopez de Prado, 2016)

Resposta ao mal-condicionamento de $\Sigma$. Três estágios:

**(a) Hierarchical Clustering.** Distância de pares: $d_{i,j} = \sqrt{(1-\rho_{i,j})/2}$ ∈ [0,1]. Distância completa por coluna: $\tilde d_{i,j} = \sqrt{\sum_n (d_{n,i} - d_{n,j})^2}$. Combina pares via single-linkage iterativamente; gera dendrograma.

**(b) Quasi-Diagonalization.** Reordena a matriz de correlação seguindo a ordem do dendrograma → clusters similares vão para a diagonal.

**(c) Recursive Bisection.** Apesar do nome "Risk Parity", usa **Inverse Variance** para distribuir peso entre lados da bisseção: $\omega^k_i = \mathrm{diag}(\Sigma^k_i)^{-1} / \mathrm{tr}(\mathrm{diag}(\Sigma^k_i)^{-1})$. Variância do bloco: $V^k_i = \omega^{k\,\prime}_i \Sigma^k_i \omega^k_i$. Fator de ajuste: $\alpha_i = 1 - V^1_i/(V^1_i + V^2_i)$.

Variações: clustering com Ward, Mahalanobis, Chebyshev; HCAA, HERC (Raffinot 2018); HRP com tail dependence (Lohre-Rother-Schäfer 2020); clustering particional (Duarte-De Castro 2020).

**Drawbacks do HRP:**
- Recursive bisection não é intuitiva e descarta parte da informação do dendrograma.
- Pesos extremos / leverage em ativos de vol baixa (US 2y) sem constraints adicionais.
- Turnover maior que RP, com $\mathrm{TO} = \tfrac{1}{(T-1)N}\sum_t\sum_i |\omega_{i,t} - \omega_{i,t-1}|$.

### 4.7 Síntese da Seção 4

Diversificação ≠ alocação igual. Risk-based mitiga problema das previsões ruins de retorno. Mas: ainda depende de $\Sigma^{-1}$ (exceto IV e HRP), ainda usa volatilidade na maioria dos casos — combinar com CVaR é desejável.

---

## 5. Robust Optimization (Shrinkage + Bayesian + Resampling)

### 5.1 Trade-off viés-variância em estimadores

$\mathrm{MSE}(\hat\theta) = \mathrm{Var}(\hat\theta) + \mathrm{Bias}(\hat\theta)^2$. Shrinkage aceita viés para reduzir variância.

### 5.2 James-Stein (para a média)

$$\hat\mu_{JS} = (1-w)\hat\mu + w\mu_0 \mathbf 1, \qquad w = \min\left(1, \frac{N-2}{T(\hat\mu - \mu_0\mathbf 1)'\Sigma^{-1}(\hat\mu - \mu_0\mathbf 1)}\right)$$

### 5.3 Ledoit-Wolf (constant correlation, para a covariância)

$$\hat\Sigma_{LW} = (1-w)\hat\Sigma + w\hat\Sigma_{CC}, \qquad w = \max\left(0, \min\left(1, \frac{\hat\kappa}{T}\right)\right)$$

com $\hat\Sigma_{CC}$ usando correlação média $\bar\rho = \tfrac{2}{N(N-1)}\sum_{i<j}\hat\rho_{i,j}$ em todas as off-diagonals, e $\hat\kappa = (\hat\pi - \hat c)/\hat\gamma$ medindo a discrepância entre estimadores.

Aviso do PDF: a intensidade do shrinkage em commodities é baixa (~0,15) → efeito modesto no MV. Bayes-Stein mais agressivo (~0,60) também não resolve o problema de raiz, porque shrinkage de momentos baixos ignora skew/curtose.

Direções modernas (Prado 2020): **Denoising** (Random Matrix Theory + Spectral Shrinkage) e **Detoning** (remoção do fator de mercado dominante).

### 5.4 Black-Litterman (Bayesian + CAPM)

**Prior** (CAPM/equilíbrio): $\Pi = \delta\Sigma\omega_M$ com $\delta = (E[R_M] - R_F)/\sigma_M^2$ (Sharpe price of risk). Alternativa risk-based: $\Pi = \delta\sigma_P \cdot \mathrm{MRC}$ (Herold 2003/2005), argumentando que estimadores de risco são mais confiáveis que de retorno.

Distribuição do prior: $P(\mu) \sim N(\Pi, \tau\Sigma)$, com $\tau$ = confiança no equilíbrio (pequeno se muita confiança).

**Likelihood (views):** $P(Q|\mu) \sim N(P\mu, \Omega)$, com $P$ matriz $K\times N$ mapeando views (absolutas ou relativas) e $\Omega$ matriz $K\times K$ de incerteza nas views. Convenção comum (He-Litterman 2002): $\Omega = \mathrm{diag}(P\Sigma P')$.

**Posterior (Bayes):**

$$\boxed{\mu_{BL} = \left[(\tau\Sigma)^{-1} + P'\Omega^{-1}P\right]^{-1}\left[(\tau\Sigma)^{-1}\Pi + P'\Omega^{-1}Q\right]}$$

$$\boxed{\Sigma_{BL} = \left[(\tau\Sigma)^{-1} + P'\Omega^{-1}P\right]^{-1}}$$

Forma alternativa via identidade de Woodbury:
$$\mu_{BL} = \Pi + \tau\Sigma P'\left[P\tau\Sigma P' + \Omega\right]^{-1}(Q - P\Pi)$$

Interpretação: shrinkage bayesiana entre $\Pi$ (mercado) e visões traduzidas pelos pesos $\tau\Sigma$ e $\Omega$.

**Críticas ao BL (Michaud-Esch-Michaud 2012, Chincarini-Kim 2012, Allaj 2013):**
- Views só lineares.
- Returns normalmente distribuídos.
- Volatilidade como única medida de risco.
- $\tau$ e $\Omega$ altamente subjetivos.
- Equilíbrio CAPM não garantido como bom proxy de "neutralidade".

Extensões: Meucci (2006) para views não-normais; Jones-Lim-Zangari (2007) para fatores; Giacometti et al (2007) usando VaR/CVaR.

### 5.5 Suggested readings (R.O.)

Litterman (2003) cap. 7; Fabozzi et al (2007) cap. 7-12; Michaud (2008) cap. 6-8 e 12 (resampling); Prado (2020) cap. 2.

### 5.6 O que falta (provavelmente parte II/III do curso)

- **Resampling** à la Michaud — mencionado nas readings mas não derivado no PDF.
- **Robust optimization** propriamente dita (worst-case / box uncertainty / ellipsoidal — Tütüncü-Koenig, Goldfarb-Iyengar).
- **Entropy pooling** (Meucci).
- **PCA / Factor Models** para redução de dimensionalidade.
- **Multi-objetivo** (Pareto, scalarização).
- **Intertemporal** (dynamic programming, HJB, Merton).

Confirmar com o usuário se virão num segundo PDF.

---

## Mapeamento técnica → biblioteca Python

| Técnica | Lib primária | Lib alternativa |
|---|---|---|
| Markowitz / MV | `PyPortfolioOpt` | `Riskfolio-Lib`, `cvxpy` |
| Utility quadrática | `cvxpy` | manual com `scipy.optimize` |
| MAD | `Riskfolio-Lib` | `scipy.optimize.linprog` (HiGHS) |
| Tracking Error | `cvxpy` | `PyPortfolioOpt` |
| Downside Risk / LPM | `Riskfolio-Lib` | manual |
| Mean-CVaR | `Riskfolio-Lib` | `cvxpy` ou `linprog` |
| Mean-CDaR | `Riskfolio-Lib` | `cvxpy` |
| IV / ERC / Risk Parity | `Riskfolio-Lib` | manual |
| Risk Budgeting | `Riskfolio-Lib` | `cvxpy` |
| HRP | `PyPortfolioOpt` (e `Riskfolio-Lib`) | scratch (scipy `linkage` + dendrogram) |
| James-Stein | `Riskfolio-Lib` (mu='jorion') | manual |
| Ledoit-Wolf | `sklearn.covariance.LedoitWolf` | `Riskfolio-Lib` |
| Black-Litterman | `PyPortfolioOpt` (`BlackLittermanModel`) | `Riskfolio-Lib`, manual |
| MILP/MINLP (ETF, custos integer) | `Pyomo` + HiGHS/Cbc/Bonmin | GEKKO |

`Riskfolio-Lib` é a escolha mais coerente com o corpus (Dany Cajas explicitamente cita Roncalli e Prado), e cobre **direto** quase todas as medidas que Chagas elenca, incluindo MAD, FLPM/SLPM, CVaR, EVaR, WR, CDaR, EDaR, UCI, ULPM, KR (Kelly Riemann). PyPortfolioOpt é mais didático, ótimo para BL e HRP.

## Constraints práticas relevantes para o SaaS

Considerando o universo BR + offshore + SaaS WCN, vão pesar:

1. **Limites por classe** (renda variável BR, RF BR, FIIs, ações offshore, ETFs offshore, ouro/cripto). Útil tanto para diversificação quanto para enquadramento regulatório.
2. **Custos de transação realistas** (B3: bps por trade + emolumentos; offshore: bps típicos). Função-objetivo com termo linear de turnover (Lobo-Fazel-Boyd).
3. **Lot sizes** para ações (round lot = 100 ações na B3; integer para ações fracionárias do mercado fracionário) → MILP.
4. **Tax-lot accounting / IR brasileiro** (15% RV, 17,5–22,5% RF). Pode entrar como custo realizado no rebalanceamento.
5. **Hedge cambial** para offshore (custo do NDF / forward).
6. **Carry de futuros** para qualquer instrumento que use rolling (mencionado explicitamente pelo Chagas).
7. **Look-ahead bias proof** no backtester — estimadores em $t$ usam só dados $\le t$.

## Pontos de atenção que o Chagas reforça

- **Linearizar sempre que possível** (MAD, CVaR, CDaR). `scipy.optimize.minimize(SLSQP)` falha em LPs grandes.
- **Tolerância numérica do solver** precisa acomodar magnitude dos retornos/covariâncias.
- **Constraints de desigualdade > equality** sempre que possível.
- **Use gradiente/Jacobiano/Hessiano explícitos** quando disponíveis.
- **Backtests sempre com look-ahead bias removido**.
- **Ex-ante vs ex-post** podem divergir muito se o rebalanceamento for raro vs janelas de medida.
- **Cobertura de cauda exige $S \ge 10^6$ cenários simulados** para CVaR confiável.

---

## Exercícios práticos (datasets esperados)

O Chagas referencia três XLSX que não vieram no PDF — provavelmente parte dos códigos de referência que você mencionou:

| Arquivo | Universo | Uso |
|---|---|---|
| `Ex1.xlsx` | 9 ações BR + CDI | MV vs EW, ±0.05/0.15, rebal 5d, 10bps, alvo 10% a.a. |
| `CVaR Example.xlsx` | 24 commodity futures | Fronteira eficiente MAD × CVaR (superfície 3D) |
| `RB Example 3.xlsx` | 24 commodity futures | MVP vs RP, daily, mensal, 2bps, alvo 5% a.a. |
