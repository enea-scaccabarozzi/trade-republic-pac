import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { BacktestConfig, MonteCarloInfo } from "@/types/api";
import { ConfigSummary } from "../config-summary";

const mockConfig: BacktestConfig = {
  strategy: "crisis_exploit",
  strategy_params: { cooldown_days: 30, severity_threshold: 0.5 },
  start_date: "2010-01-01",
  end_date: "2024-12-31",
  initial_cash: 10000,
  monthly_contribution: 500,
  pac_execution_days: [1, 15],
  settlement_fee: 1,
  spread_bps: 5,
  slippage_days: [0, 2],
  monte_carlo_iterations: 100,
  metrics: ["cagr", "sharpe", "max_drawdown"],
  benchmark: true,
};

const mockMonteCarlo: MonteCarloInfo = {
  iterations: 100,
  slippage_range: [0, 2],
};

describe("ConfigSummary", () => {
  it("is collapsed by default", () => {
    render(<ConfigSummary config={mockConfig} monteCarlo={mockMonteCarlo} />);
    expect(screen.getByText("Configuration")).toBeInTheDocument();
    // When collapsed, the strategy badge should not be visible
    expect(screen.queryByText("crisis_exploit")).not.toBeInTheDocument();
  });

  it("expands to show config fields on click", async () => {
    const user = userEvent.setup();
    render(<ConfigSummary config={mockConfig} monteCarlo={mockMonteCarlo} />);

    await user.click(screen.getByText("Configuration"));
    expect(screen.getByText("crisis_exploit")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText("1, 15")).toBeInTheDocument();
  });

  it("shows strategy params as JSON when expanded", async () => {
    const user = userEvent.setup();
    render(<ConfigSummary config={mockConfig} monteCarlo={mockMonteCarlo} />);
    await user.click(screen.getByText("Configuration"));
    expect(screen.getByText(/cooldown_days/)).toBeInTheDocument();
  });
});
