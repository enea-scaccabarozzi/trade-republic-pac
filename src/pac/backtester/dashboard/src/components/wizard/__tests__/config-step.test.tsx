import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfigStep } from "../config-step";
import type { WizardFormValues } from "../review-step";

const DEFAULT_VALUES: WizardFormValues = {
  strategy: "crisis_exploit",
  strategyParams: {},
  startDate: "2000-01-01",
  endDate: "2024-12-31",
  initialCash: 10000,
  monthlyContribution: 200,
  pacExecutionDays: "2, 16",
  settlementFee: 1,
  spreadBps: 10,
  slippageMin: 0,
  slippageMax: 2,
  monteCarloIterations: 100,
  benchmark: true,
};

describe("ConfigStep", () => {
  it("renders all form fields", () => {
    render(<ConfigStep values={DEFAULT_VALUES} onChange={vi.fn()} />);
    expect(screen.getByLabelText("Start Date")).toBeInTheDocument();
    expect(screen.getByLabelText("End Date")).toBeInTheDocument();
    expect(screen.getByLabelText(/Initial Cash/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Monthly Contribution/)).toBeInTheDocument();
    expect(screen.getByLabelText(/PAC Execution Days/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Settlement Fee/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Spread/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Min Slippage/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Max Slippage/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Iterations/)).toBeInTheDocument();
  });

  it("shows correct default values", () => {
    render(<ConfigStep values={DEFAULT_VALUES} onChange={vi.fn()} />);
    expect(screen.getByLabelText("Start Date")).toHaveValue("2000-01-01");
    expect(screen.getByLabelText("End Date")).toHaveValue("2024-12-31");
    expect(screen.getByLabelText(/Initial Cash/)).toHaveValue(10000);
    expect(screen.getByLabelText(/Monthly Contribution/)).toHaveValue(200);
    expect(screen.getByLabelText(/PAC Execution Days/)).toHaveValue("2, 16");
    expect(screen.getByLabelText(/Settlement Fee/)).toHaveValue(1);
  });

  it("calls onChange when a field is modified", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ConfigStep values={DEFAULT_VALUES} onChange={onChange} />);

    const cashInput = screen.getByLabelText(/Initial Cash/);
    await user.clear(cashInput);
    await user.type(cashInput, "20000");

    expect(onChange).toHaveBeenCalledWith("initialCash", expect.any(Number));
  });

  it("renders section headings", () => {
    render(<ConfigStep values={DEFAULT_VALUES} onChange={vi.fn()} />);
    expect(screen.getByText("Backtest Period")).toBeInTheDocument();
    expect(screen.getByText("Financial Settings")).toBeInTheDocument();
    expect(screen.getByText("Monte Carlo")).toBeInTheDocument();
  });

  it("renders benchmark toggle", () => {
    render(<ConfigStep values={DEFAULT_VALUES} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/Compare against buy-and-hold benchmark/)).toBeInTheDocument();
  });
});
