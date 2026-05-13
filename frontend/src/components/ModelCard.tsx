import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import type { ModelInfo } from "../lib/api";

const TIER_LABEL: Record<string, string> = {
  naive: "Tier 0 · Naïve",
  allocation: "Tier 1 · Allocation",
  alt_risk: "Tier 2 · Risk Measures",
  risk_budget: "Tier 3 · Risk Budgeting",
  robust: "Tier 4 · Robust",
  roadmap: "Roadmap",
};

interface Props {
  model: ModelInfo;
}

export default function ModelCard({ model }: Props) {
  return (
    <Link to={`/models/${model.name}`} className="model-card group block">
      <div className="mb-3 flex items-center justify-between">
        <span className={`tier-badge tier-badge-${model.tier}`}>
          {TIER_LABEL[model.tier] ?? model.tier}
        </span>
        <ArrowRight
          size={16}
          className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-wcn-primary"
        />
      </div>
      <h3 className="mb-1 font-serif text-xl font-semibold text-wcn-ink">
        {model.pedagogy.model_name}
      </h3>
      <p className="mb-3 text-sm text-slate-600">{model.pedagogy.one_liner}</p>
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="font-mono">{model.name}</span>
        <span>·</span>
        <span>Risco: {model.risk_measure}</span>
        {model.pedagogy.chagas_section && (
          <>
            <span>·</span>
            <span className="italic">{model.pedagogy.chagas_section}</span>
          </>
        )}
      </div>
    </Link>
  );
}
