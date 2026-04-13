import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { SignalRecord } from "@/types/api";
import { SignalActivityLog } from "../signal-activity-log";

function getTrigger(index: number): HTMLElement {
  const triggers = screen.getAllByRole("combobox");
  const el = triggers[index];
  if (!el) throw new Error(`No combobox at index ${index}`);
  return el;
}

const makeSignal = (overrides: Partial<SignalRecord> = {}): SignalRecord => ({
  date: "2024-03-01",
  rule_name: "equity_drawdown",
  severity: "warning",
  message: "Drawdown detected at 15%",
  metadata: {},
  ...overrides,
});

describe("SignalActivityLog", () => {
  it("renders table with correct row count", () => {
    const signals = [
      makeSignal({ rule_name: "rule_a", message: "Signal A" }),
      makeSignal({ rule_name: "rule_b", message: "Signal B" }),
    ];
    render(<SignalActivityLog signalLog={signals} />);
    expect(screen.getByText("Signal A")).toBeInTheDocument();
    expect(screen.getByText("Signal B")).toBeInTheDocument();
    expect(screen.getByText("2 signals")).toBeInTheDocument();
  });

  it("shows empty state when log is empty", () => {
    render(<SignalActivityLog signalLog={[]} />);
    expect(screen.getByText("No signals recorded")).toBeInTheDocument();
  });

  it("filters by text search", async () => {
    const user = userEvent.setup();
    const signals = [
      makeSignal({ message: "Alpha detected" }),
      makeSignal({ message: "Beta detected" }),
    ];
    render(<SignalActivityLog signalLog={signals} />);

    const searchInput = screen.getByPlaceholderText("Search signals...");
    await user.type(searchInput, "Alpha");

    expect(screen.getByText("Alpha detected")).toBeInTheDocument();
    expect(screen.queryByText("Beta detected")).not.toBeInTheDocument();
    expect(screen.getByText("1 of 2 signals")).toBeInTheDocument();
  });

  it("filters by rule name", async () => {
    const user = userEvent.setup();
    const signals = [
      makeSignal({ rule_name: "equity_drawdown", message: "Signal A" }),
      makeSignal({ rule_name: "yield_curve", message: "Signal B" }),
    ];
    render(<SignalActivityLog signalLog={signals} />);
    expect(screen.getByText("2 signals")).toBeInTheDocument();

    // Rule filter is the first select after the search input
    await user.click(getTrigger(0));
    const ruleOption = await screen.findByRole("option", {
      name: "yield_curve",
    });
    await user.click(ruleOption);

    expect(screen.getByText("1 of 2 signals")).toBeInTheDocument();
    expect(screen.getByText("Signal B")).toBeInTheDocument();
    expect(screen.queryByText("Signal A")).not.toBeInTheDocument();
  });

  it("filters by severity", async () => {
    const user = userEvent.setup();
    const signals = [
      makeSignal({ severity: "warning", message: "Warn signal" }),
      makeSignal({ severity: "critical", message: "Crit signal" }),
    ];
    render(<SignalActivityLog signalLog={signals} />);

    // Severity filter is the second select
    await user.click(getTrigger(1));
    const critOption = await screen.findByRole("option", { name: "critical" });
    await user.click(critOption);

    expect(screen.getByText("1 of 2 signals")).toBeInTheDocument();
    expect(screen.getByText("Crit signal")).toBeInTheDocument();
    expect(screen.queryByText("Warn signal")).not.toBeInTheDocument();
  });

  it("applies combined rule and severity filters", async () => {
    const user = userEvent.setup();
    const signals = [
      makeSignal({
        rule_name: "equity_drawdown",
        severity: "warning",
        message: "A",
      }),
      makeSignal({
        rule_name: "equity_drawdown",
        severity: "critical",
        message: "B",
      }),
      makeSignal({
        rule_name: "yield_curve",
        severity: "warning",
        message: "C",
      }),
    ];
    render(<SignalActivityLog signalLog={signals} />);
    expect(screen.getByText("3 signals")).toBeInTheDocument();

    // Filter by rule first
    await user.click(getTrigger(0));
    const ruleOption = await screen.findByRole("option", {
      name: "equity_drawdown",
    });
    await user.click(ruleOption);
    expect(screen.getByText("2 of 3 signals")).toBeInTheDocument();

    // Then filter by severity
    await user.click(getTrigger(1));
    const sevOption = await screen.findByRole("option", { name: "critical" });
    await user.click(sevOption);
    expect(screen.getByText("1 of 3 signals")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
  });
});
