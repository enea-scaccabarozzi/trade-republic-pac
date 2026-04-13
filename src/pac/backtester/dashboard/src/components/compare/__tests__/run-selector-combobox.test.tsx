import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RunSummary } from "@/types/api";
import { RunSelectorCombobox } from "../run-selector-combobox";

const makeSummary = (id: string, strategy: string): RunSummary => ({
  run_id: id,
  created_at: "2024-01-01T00:00:00Z",
  strategy,
  start_date: "2024-01-01",
  end_date: "2024-12-31",
  iterations: 100,
  final_value_median: 12000,
  cagr_median: 0.08,
  sharpe_median: 0.9,
  max_drawdown_median: -0.15,
});

describe("RunSelectorCombobox", () => {
  it("renders combobox trigger with placeholder", () => {
    const onChange = vi.fn();
    render(
      <RunSelectorCombobox
        runs={[makeSummary("r1", "crisis_exploit")]}
        selectedIds={[]}
        onSelectionChange={onChange}
      />,
    );

    expect(screen.getByText("Select runs to compare...")).toBeInTheDocument();
  });

  it("shows selected count when runs are selected", () => {
    const onChange = vi.fn();
    render(
      <RunSelectorCombobox
        runs={[makeSummary("r1", "crisis_exploit"), makeSummary("r2", "buy_and_hold")]}
        selectedIds={["r1", "r2"]}
        onSelectionChange={onChange}
      />,
    );

    expect(screen.getByText("2 runs selected")).toBeInTheDocument();
  });

  it("renders selected run badges", () => {
    const onChange = vi.fn();
    render(
      <RunSelectorCombobox
        runs={[makeSummary("r1abcdef", "crisis_exploit")]}
        selectedIds={["r1abcdef"]}
        onSelectionChange={onChange}
      />,
    );

    expect(screen.getByText(/crisis_exploit/)).toBeInTheDocument();
  });

  it("calls onSelectionChange when clearing all", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <RunSelectorCombobox
        runs={[makeSummary("r1", "crisis_exploit")]}
        selectedIds={["r1"]}
        onSelectionChange={onChange}
      />,
    );

    const clearBtn = screen.getByText("Clear all");
    await user.click(clearBtn);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("shows singular 'run' for single selection", () => {
    const onChange = vi.fn();
    render(
      <RunSelectorCombobox
        runs={[makeSummary("r1", "crisis_exploit")]}
        selectedIds={["r1"]}
        onSelectionChange={onChange}
      />,
    );

    expect(screen.getByText("1 run selected")).toBeInTheDocument();
  });
});
