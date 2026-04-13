import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RunColor } from "@/lib/run-colors";
import type { RunResult } from "@/types/api";
import { CompareEquityChart } from "../compare-equity-chart";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: ({ dataKey }: { dataKey: string }) => <div data-testid={`line-${dataKey}`} />,
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
}));

vi.mock("@/hooks/use-brush-zoom", () => ({
  useBrushZoom: () => ({
    zoom: { startIndex: 0, endIndex: 100 },
    handleBrushChange: vi.fn(),
    resetZoom: vi.fn(),
    isZoomed: false,
  }),
}));

vi.mock("@/components/charts/brush-zoom-bar", () => ({
  BrushZoomBar: () => <div data-testid="brush-zoom-bar" />,
}));

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
  metrics: {},
  equity_curve: [
    { date: "2024-01-01", p5: 9000, median: 10000, p95: 11000 },
    { date: "2024-06-01", p5: 11000, median: 12000, p95: 13000 },
  ],
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

describe("CompareEquityChart", () => {
  it("renders chart with title and description", () => {
    const runs = [makeRun("run-a", "Strategy A"), makeRun("run-b", "Strategy B")];
    render(<CompareEquityChart runs={runs} runColors={runColors} />);

    expect(screen.getByText("Equity Curves")).toBeInTheDocument();
    expect(screen.getByText("Portfolio value overlay across selected runs")).toBeInTheDocument();
  });

  it("renders a line for each run", () => {
    const runs = [makeRun("run-a", "Strategy A"), makeRun("run-b", "Strategy B")];
    render(<CompareEquityChart runs={runs} runColors={runColors} />);

    expect(screen.getByTestId("line-run-a")).toBeInTheDocument();
    expect(screen.getByTestId("line-run-b")).toBeInTheDocument();
  });

  it("shows CI Bands toggle", () => {
    const runs = [makeRun("run-a", "Strategy A")];
    render(<CompareEquityChart runs={runs} runColors={[singleColor]} />);

    expect(screen.getByText("CI Bands")).toBeInTheDocument();
  });

  it("disables CI Bands when more than 3 runs", () => {
    const ids = ["run-a", "run-b", "run-c", "run-d"];
    const runs = ids.map((id) => makeRun(id, `Strategy ${id}`));
    const colors: RunColor[] = ids.map((id, i) => ({
      runId: id,
      color: `var(--color-chart-${i + 1})`,
      label: `Strategy ${id}`,
    }));
    render(<CompareEquityChart runs={runs} runColors={colors} />);

    expect(screen.getByText(/disabled — too many runs/)).toBeInTheDocument();
  });

  it("handles empty equity curves", () => {
    const run = makeRun("run-a", "Strategy A");
    run.equity_curve = [];
    render(<CompareEquityChart runs={[run]} runColors={[singleColor]} />);

    expect(screen.getByText("Equity Curves")).toBeInTheDocument();
  });
});
