import type {
  AllocationPoint,
  EquityCurvePoint,
  MetricValue,
  SignalRecord,
  TradeRecord,
} from "@/types/api";

export interface DrawdownPoint {
  date: string;
  drawdown: number;
}

export interface FlatAllocationPoint {
  date: string;
  [assetId: string]: number | string;
}

export interface MetricDisplayInfo {
  key: string;
  label: string;
  format: "percent" | "ratio" | "decimal";
  invertColor: boolean;
}

export function computeDrawdownCurve(equityCurve: EquityCurvePoint[]): DrawdownPoint[] {
  let peak = -Infinity;
  return equityCurve.map((point) => {
    peak = Math.max(peak, point.median);
    const drawdown = peak > 0 ? (point.median - peak) / peak : 0;
    return { date: point.date, drawdown };
  });
}

export function flattenAllocations(allocations: AllocationPoint[]): {
  data: FlatAllocationPoint[];
  assetIds: string[];
} {
  if (allocations.length === 0) return { data: [], assetIds: [] };
  const firstPoint = allocations[0];
  if (!firstPoint) return { data: [], assetIds: [] };
  const assetIds = Object.keys(firstPoint.assets);
  const data = allocations.map((point) => {
    const flat: FlatAllocationPoint = { date: point.date };
    for (const id of assetIds) {
      flat[id] = point.assets[id]?.median ?? 0;
    }
    return flat;
  });
  return { data, assetIds };
}

export const METRIC_DISPLAY_MAP: Record<string, MetricDisplayInfo> = {
  cagr: { key: "cagr", label: "CAGR", format: "percent", invertColor: false },
  sharpe: {
    key: "sharpe",
    label: "Sharpe Ratio",
    format: "ratio",
    invertColor: false,
  },
  sortino: {
    key: "sortino",
    label: "Sortino Ratio",
    format: "ratio",
    invertColor: false,
  },
  calmar: {
    key: "calmar",
    label: "Calmar Ratio",
    format: "ratio",
    invertColor: false,
  },
  max_drawdown: {
    key: "max_drawdown",
    label: "Max Drawdown",
    format: "percent",
    invertColor: true,
  },
  volatility: {
    key: "volatility",
    label: "Volatility",
    format: "percent",
    invertColor: true,
  },
};

// --- Signal & Trade derivation utilities ---

export interface TradeWithAttribution extends TradeRecord {
  attributedSignals: SignalRecord[];
}

export function computeSignalAttribution(
  trades: TradeRecord[],
  signalLog: SignalRecord[],
): TradeWithAttribution[] {
  const signalsByDate = new Map<string, SignalRecord[]>();
  for (const signal of signalLog) {
    const existing = signalsByDate.get(signal.date) ?? [];
    existing.push(signal);
    signalsByDate.set(signal.date, existing);
  }

  return trades.map((trade) => ({
    ...trade,
    attributedSignals: trade.type === "hard_rebalance" ? (signalsByDate.get(trade.date) ?? []) : [],
  }));
}

export interface RuleStats {
  ruleName: string;
  triggerCount: number;
  severityBreakdown: Record<string, number>;
  firstTrigger: string;
  lastTrigger: string;
  avgFrequencyDays: number | null;
}

export function computeRuleStats(
  signalLog: SignalRecord[],
  startDate: string,
  endDate: string,
): RuleStats[] {
  const groups = new Map<string, SignalRecord[]>();
  for (const signal of signalLog) {
    const existing = groups.get(signal.rule_name) ?? [];
    existing.push(signal);
    groups.set(signal.rule_name, existing);
  }

  const totalDays = Math.max(
    1,
    (new Date(endDate).getTime() - new Date(startDate).getTime()) / (1000 * 60 * 60 * 24),
  );

  return Array.from(groups.entries()).map(([ruleName, signals]) => {
    const sorted = [...signals].sort((a, b) => a.date.localeCompare(b.date));
    const severityBreakdown: Record<string, number> = {};
    for (const s of signals) {
      severityBreakdown[s.severity] = (severityBreakdown[s.severity] ?? 0) + 1;
    }
    const first = sorted[0];
    const last = sorted[sorted.length - 1];
    return {
      ruleName,
      triggerCount: signals.length,
      severityBreakdown,
      firstTrigger: first ? first.date : "",
      lastTrigger: last ? last.date : "",
      avgFrequencyDays: signals.length > 1 ? totalDays / (signals.length - 1) : null,
    };
  });
}

export interface TradeFrequencyPoint {
  month: string;
  monthLabel: string;
  buy: number;
  sell: number;
  skipped: number;
  total: number;
}

export function computeTradeFrequency(trades: TradeRecord[]): TradeFrequencyPoint[] {
  const buckets = new Map<string, { buy: number; sell: number; skipped: number }>();

  for (const trade of trades) {
    const month = trade.date.slice(0, 7);
    const bucket = buckets.get(month) ?? { buy: 0, sell: 0, skipped: 0 };
    if (trade.skipped) {
      bucket.skipped++;
    } else if (trade.direction === "buy") {
      bucket.buy++;
    } else {
      bucket.sell++;
    }
    buckets.set(month, bucket);
  }

  return Array.from(buckets.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, counts]) => {
      const [y = "", m = ""] = month.split("-");
      const d = new Date(Number(y), Number(m) - 1);
      const label = d.toLocaleString("en-US", { month: "short" });
      return {
        month,
        monthLabel: `${label} '${y.slice(2)}`,
        ...counts,
        total: counts.buy + counts.sell + counts.skipped,
      };
    });
}

// --- Compare view derivation utilities ---

export interface NormalizedEquityPoint {
  date: string;
  [runId: string]: number | string | null;
}

export function normalizeEquityCurves(
  runs: Array<{ runId: string; equityCurve: EquityCurvePoint[] }>,
): NormalizedEquityPoint[] {
  const dateSet = new Set<string>();
  for (const run of runs) {
    for (const point of run.equityCurve) {
      dateSet.add(point.date);
    }
  }
  const allDates = Array.from(dateSet).sort();

  const runMaps = runs.map((run) => {
    const map = new Map<string, EquityCurvePoint>();
    for (const point of run.equityCurve) {
      map.set(point.date, point);
    }
    return { runId: run.runId, map };
  });

  return allDates.map((date) => {
    const point: NormalizedEquityPoint = { date };
    for (const { runId, map } of runMaps) {
      const val = map.get(date);
      point[runId] = val?.median ?? null;
      point[`${runId}_p5`] = val?.p5 ?? null;
      point[`${runId}_p95`] = val?.p95 ?? null;
    }
    return point;
  });
}

export interface SignalDensityPoint {
  month: string;
  monthLabel: string;
  count: number;
}

export interface RunSignalDensity {
  runId: string;
  label: string;
  density: SignalDensityPoint[];
  maxCount: number;
}

export function computeSignalDensity(
  runs: Array<{ runId: string; label: string; signalLog: SignalRecord[] }>,
): { densities: RunSignalDensity[]; allMonths: string[]; globalMax: number } {
  const monthSet = new Set<string>();

  const densities = runs.map((run) => {
    const buckets = new Map<string, number>();
    for (const signal of run.signalLog) {
      const month = signal.date.slice(0, 7);
      buckets.set(month, (buckets.get(month) ?? 0) + 1);
      monthSet.add(month);
    }

    const density = Array.from(buckets.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, count]) => {
        const [y, m] = month.split("-");
        const d = new Date(Number(y), Number(m) - 1);
        return {
          month,
          monthLabel: `${d.toLocaleString("en-US", { month: "short" })} '${y?.slice(2)}`,
          count,
        };
      });

    const maxCount = Math.max(0, ...density.map((d) => d.count));
    return { runId: run.runId, label: run.label, density, maxCount };
  });

  const allMonths = Array.from(monthSet).sort();
  const globalMax = Math.max(0, ...densities.map((d) => d.maxCount));

  return { densities, allMonths, globalMax };
}

export interface RadarDataPoint {
  metric: string;
  metricKey: string;
  fullMark: number;
  [runId: string]: number | string;
}

export function computeRadarData(
  runs: Array<{ runId: string; metrics: Record<string, Record<string, MetricValue>> }>,
  metricKeys: string[],
  displayMap: Record<string, { label: string; invertColor: boolean }>,
): RadarDataPoint[] {
  return metricKeys.map((key) => {
    const info = displayMap[key];
    const values = runs.map((run) => run.metrics.strategy?.[key]?.median ?? 0);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;

    const point: RadarDataPoint = {
      metric: info?.label ?? key,
      metricKey: key,
      fullMark: 100,
    };

    for (let i = 0; i < runs.length; i++) {
      const raw = values[i] ?? 0;
      const run = runs[i];
      if (!run) continue;
      let normalized = range === 0 ? 50 : ((raw - min) / range) * 100;
      if (info?.invertColor) {
        normalized = 100 - normalized;
      }
      point[run.runId] = Math.round(normalized);
      point[`_raw_${run.runId}`] = raw;
    }

    return point;
  });
}
