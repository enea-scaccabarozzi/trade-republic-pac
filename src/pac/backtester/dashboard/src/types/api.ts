export interface RunSummary {
  run_id: string;
  created_at: string;
  strategy: string;
  start_date: string;
  end_date: string;
  iterations: number;
  final_value_median: number;
  cagr_median: number | null;
  sharpe_median: number | null;
  max_drawdown_median: number | null;
}

export interface RunListResponse {
  runs: RunSummary[];
  total: number;
}

export interface RunDetailResponse {
  run: RunResult;
}

export interface StrategiesResponse {
  strategies: StrategyInfo[];
}

export interface StrategyInfo {
  name: string;
  description: string;
  params_schema: Record<string, unknown>;
}

/** Mirrors Python BacktestConfig from src/pac/backtester/config.py */
export interface StartBacktestConfig {
  strategy: string;
  strategy_params?: Record<string, unknown>;
  start_date: string;
  end_date: string;
  initial_cash?: number;
  monthly_contribution?: number;
  pac_execution_days?: number[];
  settlement_fee?: number;
  spread_bps?: number;
  slippage_days?: [number, number];
  monte_carlo_iterations?: number;
  metrics?: string[];
  benchmark?: boolean;
}

export interface StartBacktestRequest {
  config: StartBacktestConfig;
  config_path?: string;
  seed?: number;
}

export interface StartBacktestResponse {
  run_id: string;
  status: string;
}

// --- RunResult sub-types (mirrors results/models.py) ---

export interface ConfidenceInterval {
  p5: number;
  median: number;
  p95: number;
}

export interface MetricValue {
  p5: number;
  median: number;
  p95: number;
  distribution: number[] | null;
}

export interface EquityCurvePoint {
  date: string;
  p5: number;
  median: number;
  p95: number;
}

export interface AllocationPoint {
  date: string;
  assets: Record<string, ConfidenceInterval>;
}

export interface TradeRecord {
  date: string;
  type: "pac_execution" | "hard_rebalance";
  asset_id: string;
  direction: "buy" | "sell";
  amount_eur: number;
  quantity: number;
  price: number;
  fee: number;
  skipped: boolean;
}

export interface SummaryStats {
  total_invested: number;
  final_value: ConfidenceInterval;
  total_fees: ConfidenceInterval;
  total_trades: ConfidenceInterval;
  total_pac_executions: number;
}

export interface IndicatorMeta {
  key: string;
  display_name: string;
  group: string;
  kind: "continuous" | "boolean" | "event" | "ratio";
  unit: string;
  thresholds: Array<{ value: number; label: string; color: string }>;
  companion_keys: string[];
  rule_name: string;
}

export interface IndicatorDataPoint {
  date: string;
  value: number | boolean | null;
}

export interface IndicatorSeries {
  meta: IndicatorMeta;
  data: IndicatorDataPoint[];
}

export interface StrategyEventMeta {
  key: string;
  display_name: string;
  kind: "span" | "point";
  color: string;
}

export interface StrategyEvent {
  date: string;
  event_type: string;
  details: Record<string, unknown>;
  end_date: string | null;
}

export interface SignalRecord {
  date: string;
  rule_name: string;
  severity: string;
  message: string;
  metadata: Record<string, unknown>;
}

export interface MonteCarloInfo {
  iterations: number;
  slippage_range: [number, number];
}

/** BacktestConfig as returned in RunResult (all fields present, no optionals). */
export interface BacktestConfig {
  strategy: string;
  strategy_params: Record<string, unknown>;
  start_date: string;
  end_date: string;
  initial_cash: number;
  monthly_contribution: number;
  pac_execution_days: number[];
  settlement_fee: number;
  spread_bps: number;
  slippage_days: [number, number];
  monte_carlo_iterations: number;
  metrics: string[];
  benchmark: boolean;
}

export interface RunResult {
  run_id: string;
  created_at: string;
  config: BacktestConfig;
  monte_carlo: MonteCarloInfo;
  metrics: Record<string, Record<string, MetricValue>>;
  equity_curve: EquityCurvePoint[];
  allocations: AllocationPoint[];
  trades: TradeRecord[];
  summary: SummaryStats;
  signal_log: SignalRecord[];
  indicator_series: IndicatorSeries[];
  strategy_events: StrategyEvent[];
  strategy_event_meta: StrategyEventMeta[];
  benchmark_equity_curve: EquityCurvePoint[] | null;
}
