import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";

import {
  portoptAPI,
  type BacktestResponse,
  type ModelInfo,
  type OptimizationResponse,
} from "../lib/api";

const COLORS = [
  "#0F4C81", "#E07B00", "#10B981", "#8B5CF6", "#F59E0B",
  "#EF4444", "#06B6D4", "#84CC16", "#EC4899", "#6366F1",
];

export default function Workshop() {
  const [params] = useSearchParams();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(params.get("model") || "markowitz");
  const [dataset, setDataset] = useState<string>("ex1");
  const [subset, setSubset] = useState<string>("br_stocks");
  const [start, setStart] = useState<string>("2018-01-01");
  const [end, setEnd] = useState<string>("2023-12-31");
  const [maxWeight, setMaxWeight] = useState<number>(0.4);
  const [costBps, setCostBps] = useState<number>(15);

  const [opt, setOpt] = useState<OptimizationResponse | null>(null);
  const [bt, setBt] = useState<BacktestResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    portoptAPI.listModels().then(setModels);
  }, []);

  // Reset subset when dataset changes
  useEffect(() => {
    setSubset(dataset === "ex1" ? "br_stocks" : "all");
  }, [dataset]);

  async function run() {
    setBusy(true);
    setError(null);
    setOpt(null);
    setBt(null);
    try {
      const data = {
        source: "dataset" as const,
        dataset,
        subset: subset === "all" ? null : subset,
        start,
        end,
      };
      const constraints = { bounds: [0, maxWeight] as [number, number] };

      const optResp = await portoptAPI.optimize({
        model: selectedModel,
        data,
        constraints,
      });
      setOpt(optResp);

      const btResp = await portoptAPI.backtest({
        model: selectedModel,
        data,
        constraints,
        config: {
          training_window: 252,
          rebalance: "monthly",
          cost: { kind: "flat", rate_bps: costBps },
        },
      });
      setBt(btResp);
    } catch (e: any) {
      setError(e?.response?.data?.detail || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
      {/* Sidebar — controls */}
      <aside className="space-y-4 rounded-lg bg-white p-5 shadow-sm">
        <h2 className="font-serif text-xl font-semibold">Configuração</h2>

        <Field label="Modelo">
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            title="Modelos com configuração avançada (Risk Budget, Black-Litterman) requerem API direta."
          >
            {models.map((m) => {
              const isAdvanced = m.name === "risk_budget" || m.name === "black_litterman";
              return (
                <option
                  key={m.name}
                  value={m.name}
                  disabled={isAdvanced}
                >
                  {m.pedagogy.model_name}{isAdvanced ? " (avançado — via API)" : ""}
                </option>
              );
            })}
          </select>
        </Field>

        <Field label="Dataset">
          <select
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="ex1">ex1 — 24 ações BR + CDI</option>
            <option value="mdr">mdr — 24 commodities</option>
            <option value="mcvar">mcvar — 24 commodities (CVaR)</option>
          </select>
        </Field>

        <Field label="Subset">
          <select
            value={subset}
            onChange={(e) => setSubset(e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="all">Todos</option>
            {dataset === "ex1" && <option value="br_stocks">Apenas ações BR</option>}
            {dataset !== "ex1" && (
              <>
                <option value="metals">Metais</option>
                <option value="energy">Energia</option>
                <option value="agri">Agrícolas</option>
                <option value="livestock">Carne</option>
              </>
            )}
          </select>
        </Field>

        <Field label="Período">
          <div className="space-y-1">
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </div>
        </Field>

        <Field label={`Peso máximo: ${(maxWeight * 100).toFixed(0)}%`}>
          <input
            type="range"
            min={0.1}
            max={1.0}
            step={0.05}
            value={maxWeight}
            onChange={(e) => setMaxWeight(parseFloat(e.target.value))}
            className="w-full"
          />
        </Field>

        <Field label={`Custo: ${costBps} bps`}>
          <input
            type="range"
            min={0}
            max={50}
            step={1}
            value={costBps}
            onChange={(e) => setCostBps(parseInt(e.target.value))}
            className="w-full"
          />
        </Field>

        <button onClick={run} disabled={busy} className="btn btn-primary w-full">
          {busy ? "Rodando…" : "Executar"}
        </button>

        {error && (
          <div className="rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-800">
            {error}
          </div>
        )}
      </aside>

      {/* Main panel */}
      <div className="space-y-6">
        {!opt && !busy && (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center">
            <p className="text-slate-500">
              Selecione um modelo + dataset à esquerda e clique em{" "}
              <strong>Executar</strong>.
            </p>
          </div>
        )}

        {opt && (
          <section className="rounded-lg bg-white p-5 shadow-sm">
            <h3 className="mb-3 font-serif text-xl font-semibold">
              Alocação ótima — {opt.model}
            </h3>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={Object.entries(opt.weights)
                        .filter(([, v]) => v > 0.005)
                        .map(([name, value]) => ({ name, value }))}
                      dataKey="value"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      labelLine={false}
                    >
                      {Object.entries(opt.weights).map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => (v * 100).toFixed(2) + "%"} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div>
                <h4 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-500">
                  Métricas (in-sample)
                </h4>
                <dl className="text-sm">
                  <Stat label="Risco" value={`${opt.risk.toFixed(5)} (${opt.risk_measure})`} />
                  {opt.expected_return !== null && (
                    <Stat
                      label="E[R] anualizado"
                      value={`${((Math.exp(opt.expected_return * 252) - 1) * 100).toFixed(2)}%`}
                    />
                  )}
                  <Stat label="Convergiu" value={opt.converged ? "✓" : "✗"} />
                  <Stat label="Tempo" value={`${opt.elapsed_ms.toFixed(0)} ms`} />
                </dl>
              </div>
            </div>
          </section>
        )}

        {bt && (
          <section className="rounded-lg bg-white p-5 shadow-sm">
            <h3 className="mb-3 font-serif text-xl font-semibold">Backtest</h3>
            <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
              {[
                ["Sharpe", bt.metrics.sharpe?.toFixed(3)],
                ["Vol a.a.", (bt.metrics.annualized_vol * 100).toFixed(2) + "%"],
                ["Max DD", (bt.metrics.max_drawdown * 100).toFixed(2) + "%"],
                ["Total ret.", (bt.metrics.total_return * 100).toFixed(2) + "%"],
              ].map(([label, value]) => (
                <div key={label} className="rounded bg-slate-50 px-3 py-2 text-center">
                  <div className="text-xs text-slate-500">{label}</div>
                  <div className="font-semibold">{value}</div>
                </div>
              ))}
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={bt.points}>
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="cumulative_wealth"
                    stroke="#0F4C81"
                    dot={false}
                    name="Cumulative Wealth"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}
      </div>
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </div>
  );
}
