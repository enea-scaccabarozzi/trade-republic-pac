import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RunColor } from "@/lib/run-colors";
import type { MetricValue, RunResult } from "@/types/api";
import { MetricsRadarChart } from "../metrics-radar-chart";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Radar: ({ dataKey }: { dataKey: string }) => <div data-testid={`radar-${dataKey}`} />,
  PolarGrid: () => <div />,
  PolarAngleAxis: () => <div />,
  PolarRadiusAxis: () => <div />,
  Tooltip: () => <div />,
}));

const makeMetrics = (): Record<string, Record<string, MetricValue>> => ({
  strategy: {
    cagr: { p5: 0.05, median: 0.08, p95: 0.12, distribution: null },
    sharpe: { p5: 0.5, median: 0.9, p95: 1.3, distribution: null },
    sortino: { p5: 0.7, median: 1.2, p95: 1.8, distribution: null },
    calmar: { p5: 0.3, median: 0.6, p95: 1.0, distribution: null },
    max_drawdown: { p5: -0.25, median: -0.15, p95: -0.08, distribution: null },
    volatility: { p5: 0.1, median: 0.14, p95: 0.18, distribution: null },
  },
});

const makeRun = (id: string, strategy: string): RunResult => ({
  run_id: id,
  created_at: "2024-01-01T00:00:00Z",
  config: {
    strategy,
    strategy_params: {},
    start_date: "2024-01-01",
    end_date: "2024-12-31",
    initial_cash: 10000,
    monthly_contribution: 500,
    pac_execution_days: [1],
    settlement_fee: 1,
    spread_bps: 10,
    slippage_days: [0, 2],
    monte_carlo_iterations: 100,
    metrics: [],
    benchmark: false,
  },
  monte_carlo: { iterations: 100, slippage_range: [0, 2] },
  metrics: makeMetrics(),
  equity_curve: [],
  allocations: [],
  trades: [],
  summary: {
    total_invested: 6000,
    final_value: { p5: 5000, median: 6000, p95: 7000 },
    total_fees: { p5: 10, median: 12, p95: 15 },
    total_trades: { p5: 10, median: 12, p95: 15 },
    total_pac_executions: 12,
  },
  signal_log: [],
  indicator_series: [],
  strategy_events: [],
  strategy_event_meta: [],
  benchmark_equity_curve: null,
});

const singleColor: RunColor = {
  runId: "run-a",
  color: "var(--color-chart-1)",
  label: "Strategy A (run-a)",
};

const runColors: RunColor[] = [
  singleColor,
  { runId: "run-b", color: "var(--color-chart-2)", label: "Strategy B (run-b)" },
];

describe("MetricsRadarChart", () => {
  it("renders chart with title and description", () => {
    const runs = [makeRun("run-a", "Strategy A"), makeRun("run-b", "Strategy B")];
    render(<MetricsRadarChart runs={runs} runColors={runColors} />);

    expect(screen.getByText("Metrics Comparison")).toBeInTheDocument();
    expect(
      screen.getByText("Normalized 0–100 scale — higher is better for all axes"),
    ).toBeInTheDocument();
  });

  it("renders a radar polygon for each run", () => {
    const runs = [makeRun("run-a", "Strategy A"), makeRun("run-b", "Strategy B")];
    render(<MetricsRadarChart runs={runs} runColors={runColors} />);

    expect(screen.getByTestId("radar-run-a")).toBeInTheDocument();
    expect(screen.getByTestId("radar-run-b")).toBeInTheDocument();
  });

  it("shows hint for single run", () => {
    const runs = [makeRun("run-a", "Strategy A")];
    render(<MetricsRadarChart runs={runs} runColors={[singleColor]} />);

    expect(screen.getByText("Add more runs for comparison.")).toBeInTheDocument();
  });
});
