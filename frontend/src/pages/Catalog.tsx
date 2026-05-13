import { useEffect, useState } from "react";
import ModelCard from "../components/ModelCard";
import { portoptAPI, type ModelInfo, type ModelTier } from "../lib/api";

const TIER_ORDER: ModelTier[] = [
  "naive",
  "allocation",
  "alt_risk",
  "risk_budget",
  "robust",
  "roadmap",
];

const TIER_HEADER: Record<ModelTier, { title: string; description: string }> = {
  naive: {
    title: "Tier 0 · Naïve",
    description:
      "Sem otimização. Baselines que, surpreendentemente, são difíceis de bater out-of-sample.",
  },
  allocation: {
    title: "Tier 1 · Allocation-based (família Markowitz)",
    description:
      "Mean-Variance, MVP, Tangency, Utility. O canon da otimização clássica de portfólios.",
  },
  alt_risk: {
    title: "Tier 2 · Risk Measures",
    description:
      "Substituir variância por medidas que capturam melhor o que importa: MAD, Tracking Error, Downside Risk, CVaR, CDaR.",
  },
  risk_budget: {
    title: "Tier 3 · Risk Budgeting",
    description:
      "Em vez de alocar capital, aloca risco. ERC (Risk Parity), Risk Budget por grupo, Hierarchical Risk Parity.",
  },
  robust: {
    title: "Tier 4 · Robust / Bayesian",
    description:
      "Lida com ruído em μ e Σ. Shrinkage estimators, Black-Litterman, robust optimization.",
  },
  roadmap: {
    title: "Roadmap",
    description: "Modelos planejados para v2: Resampling (Michaud), Entropy Pooling.",
  },
};

export default function Catalog() {
  const [models, setModels] = useState<ModelInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    portoptAPI
      .listModels()
      .then(setModels)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!models) return <Loading />;

  const grouped = TIER_ORDER.map((tier) => ({
    tier,
    models: models.filter((m) => m.tier === tier),
  })).filter((g) => g.models.length > 0);

  return (
    <div className="space-y-10">
      <header>
        <h1 className="font-serif text-4xl font-semibold">Catálogo de modelos</h1>
        <p className="mt-2 text-slate-600">
          {models.length} modelos organizados em tiers de complexidade crescente.
          Clique em um modelo para ver sua fórmula, papers fundadores e
          experimentar no laboratório.
        </p>
      </header>

      {grouped.map(({ tier, models }) => (
        <section key={tier}>
          <div className="mb-4">
            <h2 className="font-serif text-2xl font-semibold">
              {TIER_HEADER[tier].title}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {TIER_HEADER[tier].description}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {models.map((m) => (
              <ModelCard key={m.name} model={m} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Loading() {
  return <p className="text-slate-500">Carregando catálogo…</p>;
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      Não foi possível carregar o catálogo. Detalhe: <code>{message}</code>
      <p className="mt-2 text-xs">
        Verifique se a API está rodando em <code>http://localhost:8000</code>.
      </p>
    </div>
  );
}
