/**
 * Typed client for the portopt FastAPI backend.
 *
 * The shape of the types mirrors `portopt/api/schemas.py` (Pydantic).
 * For now we mirror by hand; in the future, generate from OpenAPI.
 */
import axios from "axios";

// ---------- Types ----------

export type ModelTier =
  | "naive"
  | "allocation"
  | "alt_risk"
  | "risk_budget"
  | "robust"
  | "roadmap";

export type RiskMeasure =
  | "vol"
  | "variance"
  | "mad"
  | "downside_risk"
  | "var"
  | "cvar"
  | "cdar"
  | "tracking_error";

export interface PedagogyBlock {
  model_name: string;
  tier: ModelTier;
  one_liner: string;
  formula_latex: string;
  reference: string;
  references: string[];
  drawbacks: string[];
  when_to_use: string[];
}

export interface ModelInfo {
  name: string;
  aliases: string[];
  tier: ModelTier;
  risk_measure: RiskMeasure;
  requires_returns_history: boolean;
  supports_short: boolean;
  pedagogy: PedagogyBlock;
}

export interface DatasetInfo {
  name: string;
  description: string;
  period: string;
  exercise: string;
  subsets: Record<string, string>;
  n_assets: number;
  n_dates: number;
}

export interface DataSpec {
  source: "yfinance" | "bacen" | "dataset";
  tickers?: string[];
  start: string;
  end?: string | null;
  dataset?: string | null;
  subset?: string | null;
  log_returns_frequency?: "1D" | "5D" | "ME" | "QE";
}

export interface ConstraintsSchema {
  bounds?: [number, number];
  sum_to?: number | null;
  target_return?: number | null;
  target_vol?: number | null;
  target_risk?: number | null;
  risk_aversion?: number | null;
}

export interface ModelParams {
  alpha?: number;
  n_scenarios?: number;
  vol_estimator?: "sample" | "ewma";
  ewma_halflife?: number;
  linkage_method?: "single" | "complete" | "average" | "ward";
  risk_aversion?: number;
  approach?: "1" | "2";
  mar?: number;
  risk_free_rate?: number;
  target_te?: number;
  backend?: "scipy" | "cvxpy" | "linprog";
}

export interface OptimizeRequest {
  model: string;
  data: DataSpec;
  constraints?: ConstraintsSchema;
  params?: ModelParams;
}

export interface OptimizationResponse {
  model: string;
  weights: Record<string, number>;
  expected_return: number | null;
  risk: number;
  risk_measure: RiskMeasure;
  converged: boolean;
  diagnostics: Record<string, unknown>;
  pedagogy: PedagogyBlock | null;
  elapsed_ms: number;
}

export interface CompareRequest {
  models: { model: string; params?: ModelParams }[];
  data: DataSpec;
  constraints?: ConstraintsSchema;
  with_backtest?: boolean;
  backtest_config?: BacktestConfigSchema;
}

export interface CompareResponse {
  optimizations: Record<string, OptimizationResponse>;
  backtests?: Record<string, BacktestResponse> | null;
  summary_table: Array<Record<string, unknown>>;
  weights_table: Record<string, Record<string, number>>;
  elapsed_ms: number;
}

export interface BacktestConfigSchema {
  training_window?: number;
  rebalance?: "monthly" | "weekly" | "quarterly";
  cost?: {
    kind: "flat" | "tiered" | "b3_realistic" | "offshore" | "tax_aware" | "zero";
    rate_bps?: number;
    futures?: boolean;
  };
  initial_weights?: "equal" | "zero" | "first_alloc";
}

export interface BacktestRequest {
  model: string;
  data: DataSpec;
  constraints?: ConstraintsSchema;
  params?: ModelParams;
  config?: BacktestConfigSchema;
}

export interface BacktestPoint {
  date: string;
  log_return: number;
  cumulative_wealth: number;
  cost_paid: number;
}

export interface BacktestResponse {
  model: string;
  points: BacktestPoint[];
  rebalance_dates: string[];
  metrics: Record<string, number>;
  total_cost_paid: number;
  weights_at_end: Record<string, number>;
  pedagogy: PedagogyBlock | null;
  elapsed_ms: number;
}

// ---------- Client ----------

// API base URL:
// - Em dev: vazio → usa proxy do Vite (que redireciona /api para localhost:8000)
// - Em produção (GH Pages): https://portopt-api.fly.dev (definido em VITE_API_BASE)
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) || "";

export const api = axios.create({
  baseURL: BASE,
  timeout: 600_000,
});

// ---------- Endpoints ----------

export const portoptAPI = {
  async health() {
    const { data } = await api.get("/health");
    return data;
  },

  async listModels(): Promise<ModelInfo[]> {
    const { data } = await api.get("/api/models");
    return data;
  },

  async getModel(name: string): Promise<ModelInfo> {
    const { data } = await api.get(`/api/models/${name}`);
    return data;
  },

  async listDatasets(): Promise<DatasetInfo[]> {
    const { data } = await api.get("/api/datasets");
    return data;
  },

  async getDatasetPrices(
    name: string,
    opts?: { subset?: string; downsample?: number; start?: string; end?: string },
  ) {
    const params = new URLSearchParams();
    if (opts?.subset) params.set("subset", opts.subset);
    if (opts?.downsample) params.set("downsample", String(opts.downsample));
    if (opts?.start) params.set("start", opts.start);
    if (opts?.end) params.set("end", opts.end);
    const { data } = await api.get(`/api/datasets/${name}/prices?${params}`);
    return data;
  },

  async optimize(req: OptimizeRequest): Promise<OptimizationResponse> {
    const { data } = await api.post("/api/optimize", req);
    return data;
  },

  async backtest(req: BacktestRequest): Promise<BacktestResponse> {
    const { data } = await api.post("/api/backtest", req);
    return data;
  },

  async compare(req: CompareRequest): Promise<CompareResponse> {
    const { data } = await api.post("/api/compare", req);
    return data;
  },
};

