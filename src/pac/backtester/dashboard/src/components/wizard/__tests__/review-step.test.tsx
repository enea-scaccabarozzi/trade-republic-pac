import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { FieldMeta } from "@/lib/schema-to-zod";
import { ReviewStep, type WizardFormValues } from "../review-step";

const DEFAULT_VALUES: WizardFormValues = {
  strategy: "crisis_exploit",
  strategyParams: { cooldown_days: 30, severity_threshold: 0.5 },
  startDate: "2010-01-01",
  endDate: "2024-12-31",
  initialCash: 10000,
  monthlyContribution: 500,
  pacExecutionDays: "1, 15",
  settlementFee: 1,
  spreadBps: 5,
  slippageMin: 0,
  slippageMax: 2,
  monteCarloIterations: 100,
  benchmark: true,
};

const SCHEMA_FIELDS: FieldMeta[] = [
  {
    key: "cooldown_days",
    type: "integer",
    label: "Cooldown Days",
    description: "Days between signals",
    defaultValue: 30,
    required: true,
  },
  {
    key: "severity_threshold",
    type: "number",
    label: "Severity Threshold",
    description: "Minimum severity",
    defaultValue: 0.5,
    required: true,
  },
];

describe("ReviewStep", () => {
  const defaultProps = {
    values: DEFAULT_VALUES,
    strategyDescription: "Exploit crisis signals for better entry points.",
    schemaFields: SCHEMA_FIELDS,
    onLaunch: vi.fn(),
    isSubmitting: false,
    submitError: null,
  };

  it("renders strategy name and description", () => {
    render(<ReviewStep {...defaultProps} />);
    expect(screen.getByText("Crisis Exploit")).toBeInTheDocument();
    expect(screen.getByText(defaultProps.strategyDescription)).toBeInTheDocument();
  });

  it("renders strategy params from schema fields", () => {
    render(<ReviewStep {...defaultProps} />);
    expect(screen.getByText("Cooldown Days")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("Severity Threshold")).toBeInTheDocument();
    expect(screen.getByText("0.5")).toBeInTheDocument();
  });

  it("renders configuration section with stat badges", () => {
    render(<ReviewStep {...defaultProps} />);
    expect(screen.getByText("Configuration")).toBeInTheDocument();
    expect(screen.getByText(/2010-01-01/)).toBeInTheDocument();
    expect(screen.getByText(/2024-12-31/)).toBeInTheDocument();
    expect(screen.getByText("1, 15")).toBeInTheDocument();
  });

  it("renders simulation section", () => {
    render(<ReviewStep {...defaultProps} />);
    expect(screen.getByText("Simulation")).toBeInTheDocument();
    expect(screen.getByText("100 iterations")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
  });

  it("renders launch button", () => {
    render(<ReviewStep {...defaultProps} />);
    expect(screen.getByRole("button", { name: /Launch Backtest/i })).toBeInTheDocument();
  });

  it("disables launch button when submitting", () => {
    render(<ReviewStep {...defaultProps} isSubmitting={true} />);
    expect(screen.getByRole("button", { name: /Launch Backtest/i })).toBeDisabled();
  });

  it("shows submit error when present", () => {
    render(<ReviewStep {...defaultProps} submitError="Something went wrong" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("shows benchmark disabled text when benchmark is false", () => {
    const vals = { ...DEFAULT_VALUES, benchmark: false };
    render(<ReviewStep {...defaultProps} values={vals} />);
    expect(screen.getByText("Disabled")).toBeInTheDocument();
  });
});
