import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RunSummary } from "@/types/api";
import { SummaryBar } from "../summary-bar";

function makeRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    created_at: "2025-06-01T12:00:00Z",
    strategy: "crisis_exploit",
    start_date: "2020-01-01",
    end_date: "2025-01-01",
    iterations: 100,
    final_value_median: 15000,
    cagr_median: 0.08,
    sharpe_median: 1.2,
    max_drawdown_median: -0.15,
    ...overrides,
  };
}

describe("SummaryBar", () => {
  it("shows correct total, best CAGR, and latest run", () => {
    const runs: RunSummary[] = [
      makeRun({
        run_id: "r1",
        cagr_median: 0.08,
        strategy: "alpha",
        created_at: "2025-06-01T12:00:00Z",
      }),
      makeRun({
        run_id: "r2",
        cagr_median: 0.12,
        strategy: "beta",
        created_at: "2025-07-01T12:00:00Z",
      }),
      makeRun({
        run_id: "r3",
        cagr_median: 0.05,
        strategy: "gamma",
        created_at: "2025-05-01T12:00:00Z",
      }),
    ];
    render(<SummaryBar runs={runs} />);

    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("12.00%")).toBeInTheDocument();
    // "beta" appears in both Best CAGR and Latest Run descriptions
    expect(screen.getAllByText("beta")).toHaveLength(2);
  });

  it("shows fallback values with empty array", () => {
    render(<SummaryBar runs={[]} />);
    expect(screen.getByText("0")).toBeInTheDocument();
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });

  it("shows dash when all cagr are null", () => {
    const runs: RunSummary[] = [
      makeRun({ run_id: "r1", cagr_median: null }),
      makeRun({ run_id: "r2", cagr_median: null }),
    ];
    render(<SummaryBar runs={runs} />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });
});
