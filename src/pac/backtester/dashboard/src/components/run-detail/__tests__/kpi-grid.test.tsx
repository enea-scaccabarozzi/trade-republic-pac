import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MetricValue, SummaryStats } from "@/types/api";
import { KpiGrid } from "../kpi-grid";

const mockSummary: SummaryStats = {
  total_invested: 100000,
  final_value: { p5: 120000, median: 150000, p95: 180000 },
  total_fees: { p5: 50, median: 100, p95: 150 },
  total_trades: { p5: 20, median: 30, p95: 40 },
  total_pac_executions: 120,
};

const mockMetrics: Record<string, Record<string, MetricValue>> = {
  strategy: {
    cagr: { p5: 0.05, median: 0.08, p95: 0.12, distribution: null },
    sharpe: { p5: 0.5, median: 0.9, p95: 1.3, distribution: null },
    max_drawdown: { p5: -0.25, median: -0.15, p95: -0.08, distribution: null },
  },
};

describe("KpiGrid", () => {
  it("renders 6 KPI cards", () => {
    render(<KpiGrid summary={mockSummary} metrics={mockMetrics} />);
    expect(screen.getByText("Final Value")).toBeInTheDocument();
    expect(screen.getByText("Total Return")).toBeInTheDocument();
    expect(screen.getByText("CAGR")).toBeInTheDocument();
    expect(screen.getByText("Sharpe Ratio")).toBeInTheDocument();
    expect(screen.getByText("Max Drawdown")).toBeInTheDocument();
    expect(screen.getByText("Fees & Trades")).toBeInTheDocument();
  });

  it("shows fallback for missing metrics", () => {
    const emptyMetrics: Record<string, Record<string, MetricValue>> = {
      strategy: {},
    };
    render(<KpiGrid summary={mockSummary} metrics={emptyMetrics} />);
    // CAGR, Sharpe, Max Drawdown should show "—" fallback
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
  });
});
