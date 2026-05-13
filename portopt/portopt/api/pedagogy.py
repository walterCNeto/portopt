"""Pedagogy library — educational metadata for every model.

Each entry references the original Chagas slide deck / notebook and the
foundational academic paper. The frontend renders this as cards / tooltips
in the "learning mode" sequence.
"""

from __future__ import annotations

from portopt.api.schemas import PedagogyBlock


PEDAGOGY: dict[str, PedagogyBlock] = {
    "equal_weight": PedagogyBlock(
        model_name="Equal-Weight (1/N)",
        tier="naive",
        one_liner="Aloca peso igual em cada ativo. Naive mas surpreendentemente robusto.",
        formula_latex=r"\omega_i = \dfrac{1}{N} \quad \forall i",
        chagas_section="nb1 — usado como baseline de comparação",
        references=[
            "DeMiguel, V., Garlappi, L., Uppal, R. (2009). Optimal Versus Naive Diversification. RFS, 22(5).",
        ],
        drawbacks=[
            "Ignora completamente expectativas de retorno e estrutura de risco",
            "Pode concentrar risco em ativos voláteis",
        ],
        when_to_use=[
            "Baseline para comparar modelos sofisticados",
            "Quando estimadores de μ/Σ são muito ruidosos",
            "Portfolios com poucos ativos (N pequeno)",
        ],
    ),

    "buy_and_hold": PedagogyBlock(
        model_name="Buy-and-Hold",
        tier="naive",
        one_liner="1/N na largada, sem rebalanceamentos depois.",
        formula_latex=r"\omega_i^{(0)} = \dfrac{1}{N}, \quad \omega_i^{(t)} \text{ deriva com retornos}",
        chagas_section="nb1 — baseline passivo",
        references=[],
        drawbacks=[
            "Pesos vão derivando ao longo do tempo (drift)",
            "Ativos ganhadores ganham mais peso → concentração",
        ],
        when_to_use=[
            "Comparar contra rebalanceamento ativo",
            "Carteiras de muito longo prazo sem custos",
        ],
    ),

    "inverse_vol": PedagogyBlock(
        model_name="Inverse Volatility (IV)",
        tier="naive",
        one_liner="Peso proporcional a 1/σ. Mais peso em ativos menos voláteis.",
        formula_latex=r"\omega_i = \dfrac{1/\sigma_i}{\sum_j 1/\sigma_j}",
        chagas_section="PDF §4.2, nb3",
        references=[
            "Asness, C., Frazzini, A., Pedersen, L. (2012). Leverage Aversion and Risk Parity. FAJ.",
        ],
        drawbacks=[
            "Ignora correlações entre ativos",
            "Caso particular degenerado do Risk Parity",
        ],
        when_to_use=[
            "Quando Σ é mal-condicionada (universo com correlações altas)",
            "Como warm-start para Risk Parity",
        ],
    ),

    "markowitz": PedagogyBlock(
        model_name="Markowitz Mean-Variance",
        tier="allocation",
        one_liner="O clássico: maximizar retorno esperado para um nível de risco (volatilidade).",
        formula_latex=r"""\begin{aligned}
\min_\omega & \quad \omega' \Sigma \omega \\
\text{s.t.} & \quad \omega' \mathbf{1} = 1,\; \omega'\bar R \geq \mu_{tgt}
\end{aligned}""",
        chagas_section="PDF §2, nb1",
        references=[
            "Markowitz, H. (1952). Portfolio Selection. Journal of Finance, 7(1).",
            "Kolm, P., Tütüncü, R., Fabozzi, F. (2014). 60 Years of Portfolio Optimization. EJOR.",
        ],
        drawbacks=[
            "Volatilidade é medida de dispersão, não de risco propriamente dito",
            "Sensível a erros em μ̂ — Michaud (1998) chama de 'error maximizer'",
            "Σ⁻¹ amplifica ruído se ativos são correlacionados",
            "Soluções não são únicas — pode haver portfolios diferentes com mesmo (μ, σ)",
        ],
        when_to_use=[
            "Retornos quasi-normais e simétricos",
            "Janela curta o suficiente para μ̂ ser razoável (≤ 1 ano momentum)",
            "Universo com correlações moderadas",
        ],
    ),

    "min_variance": PedagogyBlock(
        model_name="Minimum Variance Portfolio (MVP)",
        tier="allocation",
        one_liner="O portfólio de menor variância na fronteira eficiente. Independe de μ.",
        formula_latex=r"\omega_{MVP} = \dfrac{\Sigma^{-1} \mathbf{1}}{\mathbf{1}' \Sigma^{-1} \mathbf{1}}",
        chagas_section="PDF §2.2, nb1",
        references=[
            "Clarke, R., de Silva, H., Thorley, S. (2006). Minimum-Variance Portfolios in US Equity Market. JPM.",
        ],
        drawbacks=[
            "Mesmas vulnerabilidades do MV em relação a Σ̂",
            "Tende a concentrar em ativos de baixa volatilidade",
        ],
        when_to_use=[
            "Quando expectativas de retorno são pouco confiáveis",
            "Estratégia de baixa volatilidade (low-vol anomaly)",
        ],
    ),

    "max_sharpe": PedagogyBlock(
        model_name="Maximum Sharpe (Tangency Portfolio)",
        tier="allocation",
        one_liner="Maximiza Sharpe ratio. O portfolio tangente à fronteira eficiente com taxa livre de risco.",
        formula_latex=r"\omega_T = \dfrac{\Sigma^{-1}(\bar R - R_F \mathbf{1})}{\mathbf{1}' \Sigma^{-1}(\bar R - R_F \mathbf{1})}",
        chagas_section="PDF §2.4 (Tobin Separation), nb1",
        references=[
            "Tobin, J. (1958). Liquidity Preference as Behavior Towards Risk. RES, 25.",
            "Sharpe, W. (1966). Mutual Fund Performance. J. Business, 39.",
        ],
        drawbacks=[
            "Mesma sensibilidade do MV a μ̂",
            "Sharpe in-sample ≠ Sharpe out-of-sample (Lo 2002)",
        ],
        when_to_use=[
            "Quando há ativo livre de risco bem definido (CDI/SELIC no Brasil)",
            "Decomposição estratégia + tática (Tobin)",
        ],
    ),

    "utility": PedagogyBlock(
        model_name="Quadratic Utility",
        tier="allocation",
        one_liner="Maximiza utilidade quadrática U = R - 0.5λσ². Parâmetro λ traduz aversão a risco.",
        formula_latex=r"\max_\omega \quad \bar R'\omega - \dfrac{1}{2}\lambda\, \omega'\Sigma\omega",
        chagas_section="PDF §2.5, nb1",
        references=[
            "von Neumann, J., Morgenstern, O. (1947). Theory of Games and Economic Behavior.",
        ],
        drawbacks=[
            "Utilidade quadrática implica aversão crescente — pouco realista para wealth crescente",
            "Não captura skew/kurtose nas preferências do investidor",
        ],
        when_to_use=[
            "Investidor com perfil de risco bem definido",
            "Aproximação de outras utilidades via Taylor de 2ª ordem em torno de E[R]",
        ],
    ),

    "mad": PedagogyBlock(
        model_name="Mean-Absolute Deviation (MAD)",
        tier="alt_risk",
        one_liner="Substitui variância por MAD. Não precisa de Σ; problema vira LP.",
        formula_latex=r"""\begin{aligned}
\min_{\omega, y, z} & \quad \sum_{t=1}^T (y_t + z_t) \\
\text{s.t.} & \quad y_t - z_t = \sum_i (r_{t,i} - \mu_i)\omega_i,\quad y_t, z_t \geq 0
\end{aligned}""",
        chagas_section="PDF §3.2, nb2",
        references=[
            "Konno, H., Yamazaki, H. (1991). MAD Portfolio Optimization Model. Management Science, 37.",
        ],
        drawbacks=[
            "Como variância, é medida de dispersão (não de risco strict sense)",
            "Em distribuições simétricas dá resultados muito similares ao MV",
        ],
        when_to_use=[
            "Universos grandes (N ≥ 100): LP escala muito melhor que QP",
            "Quando estimar Σ é caro/instável",
            "Quando desejamos alocações mais parsimoniosas",
        ],
    ),

    "tracking_error": PedagogyBlock(
        model_name="Tracking Error",
        tier="alt_risk",
        one_liner="Minimiza desvio padrão dos excessos sobre um benchmark.",
        formula_latex=r"TE = \sqrt{(\omega_P - \omega_B)' \Sigma (\omega_P - \omega_B)}",
        chagas_section="PDF §3.3, nb2",
        references=[
            "Jorion, P. (2003). Portfolio Optimization with Tracking-Error Constraints. FAJ.",
        ],
        drawbacks=[
            "TE baixo não significa risco absoluto baixo",
            "Ex-ante e ex-post podem divergir muito sem rebalanceamento frequente",
        ],
        when_to_use=[
            "Estratégias passivas (ETFs)",
            "Active management com constraint de aderência ao benchmark",
            "Smart beta / enhanced indexing",
        ],
    ),

    "downside_risk": PedagogyBlock(
        model_name="Mean-Downside-Risk",
        tier="alt_risk",
        one_liner="Penaliza apenas retornos abaixo de um MAR (Minimum Acceptable Return).",
        formula_latex=r"DR = \sqrt{\dfrac{1}{T-1}\sum_{t=1}^T \min(r_{t,P} - \text{MAR}, 0)^2}",
        chagas_section="PDF §3.4, nb2",
        references=[
            "Sortino, F., van der Meer, R. (1991). Downside Risk. JPM, 17(4).",
            "Harlow, W.V. (1991). Asset Allocation in a Downside-Risk Framework. FAJ.",
        ],
        drawbacks=[
            "Resultados parecidos com MV quando retornos são simétricos",
            "Sensível à escolha do MAR",
        ],
        when_to_use=[
            "Retornos assimétricos (skew negativo claro)",
            "Investidor com aversão a perdas (loss aversion)",
            "Sortino-style portfolio construction",
        ],
    ),

    "cvar": PedagogyBlock(
        model_name="Mean-CVaR (Conditional VaR)",
        tier="alt_risk",
        one_liner="Minimiza a perda esperada na cauda (média das α% piores realizações).",
        formula_latex=r"""\text{CVaR}_\alpha(\omega) = \min_{z}\left[ z + \dfrac{1}{\alpha} \mathbb{E}[(-R_P - z)^+] \right]""",
        chagas_section="PDF §3.5, nb2",
        references=[
            "Rockafellar, R., Uryasev, S. (2000). Optimization of Conditional Value-at-Risk. J. Risk, 2(3).",
            "Acerbi, C., Tasche, D. (2002). Expected Shortfall: A Natural Coherent Alternative to VaR.",
        ],
        drawbacks=[
            "Precisa de muitos cenários para estimar a cauda (S ≥ 10⁶ recomendado)",
            "Multivariada Normal sub-estima cauda — use cenários históricos ou copulas",
            "Solução tende a portfolios concentrados",
        ],
        when_to_use=[
            "Retornos com cauda pesada (FX, crédito, cripto)",
            "Quando o regulador exige métricas coerentes (VaR não é coerente)",
            "Tail-risk parity / Stress-aware portfolio construction",
        ],
    ),

    "cdar": PedagogyBlock(
        model_name="Mean-CDaR (Conditional Drawdown-at-Risk)",
        tier="alt_risk",
        one_liner="CVaR aplicado sobre drawdowns: média dos α% piores drawdowns.",
        formula_latex=r"\text{CDaR}_\alpha(\omega) = \min_z\left[ z + \dfrac{1}{T\alpha} \sum_t (DD_t(\omega) - z)^+ \right]",
        chagas_section="PDF §3.6 (não implementado nos notebooks)",
        references=[
            "Chekhlov, A., Uryasev, S., Zabarankin, M. (2003). Drawdown Measure in Portfolio Optimization.",
        ],
        drawbacks=[
            "Path-dependent: requer modelagem cuidadosa de autocorrelações",
            "Requer série longa para distribuição de drawdowns ser confiável",
        ],
        when_to_use=[
            "Investidor preocupado com sustained losses, não só single-period",
            "Hedge funds, managed accounts com benchmarks de drawdown",
        ],
    ),

    "erc": PedagogyBlock(
        model_name="Equal Risk Contribution (ERC) / Risk Parity",
        tier="risk_budget",
        one_liner="Cada ativo contribui exatamente vol_P/N para a vol total. Diversificação em risco, não em alocação.",
        formula_latex=r"""\min_\omega \sum_i \left( \omega_i \dfrac{(\Sigma\omega)_i}{\omega'\Sigma\omega} - \dfrac{1}{N} \right)^2""",
        chagas_section="PDF §4.4, nb3",
        references=[
            "Maillard, S., Roncalli, T., Teiletche, J. (2010). The Properties of Equally Weighted Risk Contribution Portfolios. JPM.",
            "Qian, E. (2005). Risk Parity Portfolios.",
        ],
        drawbacks=[
            "Em alvos de vol altos, alavanca demais ativos de baixa vol (US 2y)",
            "Múltiplos mínimos locais → warm-start importa (IV é padrão)",
            "Ainda usa Σ⁻¹ implicitamente",
        ],
        when_to_use=[
            "Diversificação genuína (não 'concentração disfarçada')",
            "Universos heterogêneos (ações + bonds + commodities)",
            "Quando expectativas de retorno são pouco confiáveis",
        ],
    ),

    "risk_budget": PedagogyBlock(
        model_name="Risk Budgeting (por grupo)",
        tier="risk_budget",
        one_liner="Generaliza ERC: cada grupo de ativos contribui com um budget específico.",
        formula_latex=r"\sum_{i \in G_k} \omega_i \dfrac{(\Sigma\omega)_i}{\omega'\Sigma\omega} = RB_k, \; \forall k",
        chagas_section="PDF §4.5, nb3",
        references=[
            "Bruder, B., Roncalli, T. (2012). Managing Risk Exposures using the Risk Budgeting Approach.",
            "Roncalli, T. (2013). Introduction to Risk Parity and Budgeting.",
        ],
        drawbacks=[
            "Approach 1 (hard) pode ser infeasible",
            "Approach 2 (soft) não garante budgets exatos",
            "Calibração de budgets é subjetiva",
        ],
        when_to_use=[
            "Alocação top-down por classe de ativo",
            "Implementação de tese de investimento (X% em macro, Y% em fatores, ...)",
            "Compliance com mandato de risco regulamentado",
        ],
    ),

    "hrp": PedagogyBlock(
        model_name="Hierarchical Risk Parity (HRP)",
        tier="risk_budget",
        one_liner="Clustering hierárquico + recursive bisection. Evita Σ⁻¹ direto.",
        formula_latex=r"""\begin{aligned}
\text{1. } & d_{ij} = \sqrt{(1-\rho_{ij})/2} \rightarrow \text{linkage} \\
\text{2. } & \text{Quasi-diagonalize } \Sigma \\
\text{3. } & \text{Bisection com IV em cada cluster}
\end{aligned}""",
        chagas_section="PDF §4.6, nb3",
        references=[
            "López de Prado, M. (2016). Building Diversified Portfolios that Outperform Out-of-Sample. JPM.",
            "Raffinot, T. (2018). Hierarchical Clustering-Based Asset Allocation. JPM.",
        ],
        drawbacks=[
            "Recursive bisection descarta parte da informação do dendrograma",
            "Pesos extremos para ativos de baixa volatilidade",
            "Turnover mais alto que RP (custos!)",
        ],
        when_to_use=[
            "Universos grandes (N ≥ 50)",
            "Σ mal-condicionada (correlações altas)",
            "Quando interpretabilidade do dendrograma é valor agregado",
        ],
    ),

    "black_litterman": PedagogyBlock(
        model_name="Black-Litterman",
        tier="robust",
        one_liner="Combina equilíbrio de mercado (CAPM) com views via Bayes. Aloca de forma mais estável.",
        formula_latex=r"""\mu_{BL} = [(\tau\Sigma)^{-1} + P'\Omega^{-1}P]^{-1}[(\tau\Sigma)^{-1}\Pi + P'\Omega^{-1}Q]""",
        chagas_section="PDF §5.4, nb4",
        references=[
            "Black, F., Litterman, R. (1992). Global Portfolio Optimization. FAJ, 48(5).",
            "He, G., Litterman, R. (2002). The Intuition Behind Black-Litterman Model Portfolios.",
            "Meucci, A. (2005). Risk and Asset Allocation. Springer.",
        ],
        drawbacks=[
            "Views só lineares (Meucci 2006 estende)",
            "τ e Ω são subjetivos",
            "CAPM equilibrium assume mercado eficiente",
            "Ainda assume retornos normais",
        ],
        when_to_use=[
            "Quando há expertise / visão clara sobre alguns ativos",
            "Combinação de gestão tática + estratégica",
            "Multi-asset, multi-currency portfolios",
        ],
    ),
}


def get_pedagogy(model_name: str) -> PedagogyBlock | None:
    """Lookup pedagogy by canonical model name (no aliases)."""
    return PEDAGOGY.get(model_name)
