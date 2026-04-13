import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MetricValue } from "@/types/api";
import { MetricsTable } from "../metrics-table";

const strategyMetrics: Record<string, MetricValue> = {
  cagr: { p5: 0.05, median: 0.08, p95: 0.12, distribution: null },
  sharpe: { p5: 0.5, median: 0.9, p95: 1.3, distribution: null },
  max_drawdown: { p5: -0.25, median: -0.15, p95: -0.08, distribution: null },
  volatility: { p5: 0.1, median: 0.14, p95: 0.18, distribution: null },
};

const benchmarkMetrics: Record<string, MetricValue> = {
  cagr: { p5: 0.04, median: 0.06, p95: 0.09, distribution: null },
  sharpe: { p5: 0.4, median: 0.7, p95: 1.0, distribution: null },
  max_drawdown: { p5: -0.3, median: -0.2, p95: -0.12, distribution: null },
  volatility: { p5: 0.12, median: 0.16, p95: 0.2, distribution: null },
};

describe("MetricsTable", () => {
  it("renders rows for each metric", () => {
    const metrics = { strategy: strategyMetrics, benchmark: benchmarkMetrics };
    render(<MetricsTable metrics={metrics} />);
    expect(screen.getByText("CAGR")).toBeInTheDocument();
    expect(screen.getByText("Sharpe Ratio")).toBeInTheDocument();
    expect(screen.getByText("Max Drawdown")).toBeInTheDocument();
    expect(screen.getByText("Volatility")).toBeInTheDocument();
  });

  it("shows delta column when benchmark exists", () => {
    const metrics = { strategy: strategyMetrics, benchmark: benchmarkMetrics };
    render(<MetricsTable metrics={metrics} />);
    expect(screen.getByText("Delta")).toBeInTheDocument();
    expect(screen.getByText("Benchmark")).toBeInTheDocument();
  });

  it("hides benchmark and delta columns when no benchmark", () => {
    const metrics = { strategy: strategyMetrics };
    render(<MetricsTable metrics={metrics} />);
    expect(screen.queryByText("Delta")).not.toBeInTheDocument();
    expect(screen.queryByText("Benchmark")).not.toBeInTheDocument();
  });

  it("returns null when no metrics", () => {
    const { container } = render(<MetricsTable metrics={{}} />);
    expect(container.firstChild).toBeNull();
  });
});
