import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { StrategyInfo } from "@/types/api";
import { StrategyPicker } from "../strategy-picker";

const STRATEGIES: StrategyInfo[] = [
  {
    name: "basic_pac",
    description: "Simple periodic investment plan",
    params_schema: {},
  },
  {
    name: "crisis_exploit",
    description: "Exploit crisis signals for entry",
    params_schema: {
      type: "object",
      properties: {
        cooldown_days: { type: "integer", default: 30 },
      },
    },
  },
];

describe("StrategyPicker", () => {
  const defaultProps = {
    strategies: STRATEGIES,
    selectedStrategy: null,
    onSelectStrategy: vi.fn(),
    strategyParams: {},
    onParamChange: vi.fn(),
    schemaFields: null,
  };

  it("renders available strategies", () => {
    render(<StrategyPicker {...defaultProps} />);
    expect(screen.getByText("Basic Pac")).toBeInTheDocument();
    expect(screen.getByText("Crisis Exploit")).toBeInTheDocument();
    expect(screen.getByText("Simple periodic investment plan")).toBeInTheDocument();
    expect(screen.getByText("Exploit crisis signals for entry")).toBeInTheDocument();
  });

  it("calls onSelectStrategy when a strategy is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<StrategyPicker {...defaultProps} onSelectStrategy={onSelect} />);

    await user.click(screen.getByText("Basic Pac"));
    expect(onSelect).toHaveBeenCalledWith("basic_pac");
  });

  it("renders heading and description text", () => {
    render(<StrategyPicker {...defaultProps} />);
    expect(screen.getByText("Choose a Strategy")).toBeInTheDocument();
    expect(
      screen.getByText("Select a backtest strategy and configure its parameters."),
    ).toBeInTheDocument();
  });

  it("shows strategy parameters section when strategy is selected with schema fields", () => {
    const fields = [
      {
        key: "cooldown_days",
        type: "integer" as const,
        label: "Cooldown Days",
        description: "Days between signals",
        defaultValue: 30,
        required: true,
      },
    ];
    render(
      <StrategyPicker
        {...defaultProps}
        selectedStrategy="crisis_exploit"
        schemaFields={fields}
        strategyParams={{ cooldown_days: 30 }}
      />,
    );
    expect(screen.getByText("Strategy Parameters")).toBeInTheDocument();
    expect(screen.getByText("Cooldown Days")).toBeInTheDocument();
  });

  it("does not show parameters section when no strategy is selected", () => {
    render(<StrategyPicker {...defaultProps} />);
    expect(screen.queryByText("Strategy Parameters")).not.toBeInTheDocument();
  });
});
