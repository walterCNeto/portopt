import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

import { portoptAPI, type CompareResponse, type ModelInfo } from "../lib/api";

const COLORS = [
  "#0F4C81", "#E07B00", "#10B981", "#8B5CF6", "#F59E0B",
  "#EF4444", "#06B6D4", "#84CC16",
];

export default function Compare() {
  const [params] = useSearchParams();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<string[]>(
    params.get("models")?.split(",") ?? ["ew", "markowitz", "hrp"],
  );
  const [dataset, setDataset] = useState("ex1");
  const [subset, setSubset] = useState("br_stocks");
  const [withBacktest, setWithBacktest] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    portoptAPI.listModels().then(setModels);
  }, []);

  async function run() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await portoptAPI.compare({
        models: selected.map((m) => ({ model: m })),
        data: {
          source: "dataset",
          dataset,
          subset: subset === "all" ? null : subset,
          start: "2018-01-01",
          end: "2023-12-31",
        },
        constraints: { bounds: [0, 0.4] },
        with_backtest: withBacktest,
        backtest_config: {
          training_window: 252,
          rebalance: "monthly",
          cost: { kind: "flat", rate_bps: 15 },
        },
      });
      setResult(r);
    } catch (e: any) {
      setError(e?.response?.data?.detail || String(e));
    } finally {
      setBusy(false);
    }
  }

  function toggleModel(name: string) {
    setSelected((s) =>
      s.includes(name) ? s.filter((x) => x !== name) : [...s, name].slice(0, 8),
    );
  }

  const wealthData = useMemo(() => {
    if (!result?.backtests) return null;
    // Build a long-form array where each timestamp has values per model
    const byDate: Record<string, Record<string, number>> = {};
    for (const [modelName, bt] of Object.entries(result.backtests)) {
      for (const p of bt.points) {
        byDate[p.date] = byDate[p.date] || { date: p.date } as any;
        byDate[p.date][modelName] = p.cumulative_wealth;
      }
    }
    return Object.values(byDate).sort((a: any, b: any) =>
      a.date < b.date ? -1 : 1,
    );
  }, [result]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-serif text-4xl font-semibold">Comparar modelos</h1>
        <p className="mt-1 text-slate-600">
          Rode até 8 modelos no mesmo dataset e veja pesos + métricas lado a lado.
        </p>
      </header>

      {/* Controls */}
      <section className="rounded-lg bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
          Modelos selecionados ({selected.length} / 8)
        </h2>
        <div className="mb-4 flex flex-wrap gap-2">
          {models.map((m) => {
            const active = selected.includes(m.name);
            return (
              <button
                key={m.name}
                onClick={() => toggleModel(m.name)}
                className={`rounded-full border px-3 py-1 text-xs transition ${
                  active
                    ? "border-wcn-primary bg-wcn-primary text-white"
                    : "border-slate-300 bg-white text-slate-600 hover:border-wcn-primary"
                }`}
              >
                {m.pedagogy.model_name}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-end gap-3 border-t border-slate-100 pt-3">
          <Field label="Dataset">
            <select
              value={dataset}
              onChange={(e) => {
                setDataset(e.target.value);
                setSubset(e.target.value === "ex1" ? "br_stocks" : "all");
              }}
              className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value="ex1">ex1</option>
              <option value="mdr">mdr</option>
              <option value="mcvar">mcvar</option>
            </select>
          </Field>
          <Field label="Subset">
            <select
              value={subset}
              onChange={(e) => setSubset(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value="all">Todos</option>
              {dataset === "ex1" && <option value="br_stocks">Ações BR</option>}
              {dataset !== "ex1" && (
                <>
                  <option value="metals">Metais</option>
                  <option value="energy">Energia</option>
                  <option value="agri">Agrícolas</option>
                </>
              )}
            </select>
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={withBacktest}
              onChange={(e) => setWithBacktest(e.target.checked)}
            />
            Incluir backtest mensal (15 bps)
          </label>
          <button
            onClick={run}
            disabled={busy || selected.length < 2}
            className="btn btn-primary ml-auto"
          >
            {busy ? "Rodando…" : "Comparar"}
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      {result && (
        <>
          {/* Summary table */}
          <section className="rounded-lg bg-white p-5 shadow-sm">
            <h3 className="mb-3 font-serif text-xl font-semibold">Resumo</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left">
                    <th className="py-2">Modelo</th>
                    <th>Risco</th>
                    <th>E[R] diário</th>
                    <th>Medida</th>
                    <th>#ativos</th>
                    <th>Peso máx</th>
                  </tr>
                </thead>
                <tbody>
                  {result.summary_table.map((row, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="py-2 font-mono">{row.model as string}</td>
                      <td>{typeof row.risk === "number" ? row.risk.toFixed(5) : "—"}</td>
                      <td>{typeof row.expected_return === "number" ? row.expected_return.toFixed(5) : "—"}</td>
                      <td className="text-xs text-slate-500">
                        {row.risk_measure as string}
                      </td>
                      <td>{row.n_active as number}</td>
                      <td>
                        {typeof row.max_weight === "number"
                          ? (row.max_weight * 100).toFixed(1) + "%"
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Backtest wealth */}
          {wealthData && (
            <section className="rounded-lg bg-white p-5 shadow-sm">
              <h3 className="mb-3 font-serif text-xl font-semibold">
                Wealth path (backtest)
              </h3>
              <div className="h-72">
                <ResponsiveContainer>
                  <LineChart data={wealthData as any[]}>
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    {Object.keys(result.backtests || {}).map((m, i) => (
                      <Line
                        key={m}
                        type="monotone"
                        dataKey={m}
                        stroke={COLORS[i % COLORS.length]}
                        dot={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {/* Backtest metrics table */}
          {result.backtests && (
            <section className="rounded-lg bg-white p-5 shadow-sm">
              <h3 className="mb-3 font-serif text-xl font-semibold">
                Métricas comparadas
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left">
                      <th className="py-2">Métrica</th>
                      {Object.keys(result.backtests).map((m) => (
                        <th key={m} className="font-mono">
                          {m}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      "total_return",
                      "annualized_return",
                      "annualized_vol",
                      "sharpe",
                      "sortino",
                      "max_drawdown",
                      "ulcer_index",
                    ].map((metric) => (
                      <tr key={metric} className="border-b border-slate-100">
                        <td className="py-2 text-slate-600">{metric}</td>
                        {Object.entries(result.backtests!).map(([_, bt]) => (
                          <td key={metric + bt.model} className="font-mono">
                            {bt.metrics[metric]?.toFixed(4)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-slate-500">
        {label}
      </label>
      {children}
    </div>
  );
}
