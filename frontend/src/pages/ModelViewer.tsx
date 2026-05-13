import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, FlaskConical, GitCompare } from "lucide-react";

import PedagogyBlock from "../components/PedagogyBlock";
import { portoptAPI, type ModelInfo } from "../lib/api";

export default function ModelViewer() {
  const { name = "" } = useParams<{ name: string }>();
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setModel(null);
    setError(null);
    portoptAPI
      .getModel(name)
      .then(setModel)
      .catch((e) => setError(String(e)));
  }, [name]);

  if (error) {
    return (
      <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-rose-800">
        Modelo não encontrado: <code>{name}</code>
      </div>
    );
  }
  if (!model) return <p className="text-slate-500">Carregando…</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link
        to="/catalog"
        className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-wcn-primary"
      >
        <ArrowLeft size={14} /> voltar ao catálogo
      </Link>

      <header>
        <span className={`tier-badge tier-badge-${model.tier} mb-2`}>{model.tier}</span>
        <h1 className="mt-2 font-serif text-4xl font-semibold">
          {model.pedagogy.model_name}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500">
          <code className="rounded bg-slate-100 px-2 py-0.5 font-mono">{model.name}</code>
          {model.aliases.length > 0 && (
            <span>
              aliases:{" "}
              {model.aliases.map((a) => (
                <code key={a} className="mr-1 rounded bg-slate-100 px-1 font-mono text-xs">
                  {a}
                </code>
              ))}
            </span>
          )}
          <span>·</span>
          <span>Risco: {model.risk_measure}</span>
          <span>·</span>
          <span>{model.supports_short ? "permite short" : "long-only"}</span>
        </div>
      </header>

      <PedagogyBlock data={model.pedagogy} />

      {/* Quick actions */}
      <section className="rounded-lg bg-white p-5 shadow-sm">
        <h3 className="mb-3 font-serif text-lg font-semibold">Experimente</h3>
        <div className="flex gap-3">
          <Link
            to={`/workshop?model=${model.name}`}
            className="btn btn-primary inline-flex items-center gap-2"
          >
            <FlaskConical size={16} />
            Abrir no laboratório
          </Link>
          <Link
            to={`/compare?models=${model.name},markowitz,ew`}
            className="btn btn-secondary inline-flex items-center gap-2"
          >
            <GitCompare size={16} />
            Comparar com Markowitz e EW
          </Link>
        </div>
      </section>
    </div>
  );
}
