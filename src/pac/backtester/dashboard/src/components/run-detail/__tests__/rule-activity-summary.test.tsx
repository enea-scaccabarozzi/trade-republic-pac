import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SignalRecord } from "@/types/api";
import { RuleActivitySummary } from "../rule-activity-summary";

const makeSignal = (overrides: Partial<SignalRecord> = {}): SignalRecord => ({
  date: "2024-03-01",
  rule_name: "equity_drawdown",
  severity: "warning",
  message: "Drawdown detected",
  metadata: {},
  ...overrides,
});

describe("RuleActivitySummary", () => {
  it("renders one card per rule", () => {
    const signals = [
      makeSignal({ rule_name: "equity_drawdown", date: "2024-01-01" }),
      makeSignal({ rule_name: "equity_drawdown", date: "2024-02-01" }),
      makeSignal({ rule_name: "yield_curve", date: "2024-01-15" }),
    ];
    render(<RuleActivitySummary signalLog={signals} startDate="2024-01-01" endDate="2024-04-01" />);
    expect(screen.getByText("Equity Drawdown")).toBeInTheDocument();
    expect(screen.getByText("Yield Curve")).toBeInTheDocument();
  });

  it("shows correct trigger count", () => {
    const signals = [
      makeSignal({ rule_name: "test_rule", date: "2024-01-01" }),
      makeSignal({ rule_name: "test_rule", date: "2024-02-01" }),
      makeSignal({ rule_name: "test_rule", date: "2024-03-01" }),
    ];
    render(<RuleActivitySummary signalLog={signals} startDate="2024-01-01" endDate="2024-04-01" />);
    expect(screen.getByText("3 triggers")).toBeInTheDocument();
  });

  it("shows severity breakdown badges", () => {
    const signals = [
      makeSignal({ severity: "warning", date: "2024-01-01" }),
      makeSignal({ severity: "critical", date: "2024-02-01" }),
    ];
    render(<RuleActivitySummary signalLog={signals} startDate="2024-01-01" endDate="2024-04-01" />);
    expect(screen.getByText("warning")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
  });

  it("shows Single occurrence for single trigger", () => {
    const signals = [makeSignal({ date: "2024-02-01" })];
    render(<RuleActivitySummary signalLog={signals} startDate="2024-01-01" endDate="2024-04-01" />);
    expect(screen.getByText("Single occurrence")).toBeInTheDocument();
  });
});
