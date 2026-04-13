import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RunResult, TradeRecord } from "@/types/api";
import { TradesTab } from "../trades-tab";

function getTrigger(index: number): HTMLElement {
  const triggers = screen.getAllByRole("combobox");
  const el = triggers[index];
  if (!el) throw new Error(`No combobox at index ${index}`);
  return el;
}

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count, estimateSize }: { count: number; estimateSize: () => number }) => {
    const size = estimateSize();
    return {
      getVirtualItems: () =>
        Array.from({ length: count }, (_, i) => ({
          index: i,
          key: i,
          start: i * size,
          end: (i + 1) * size,
          size,
          lane: 0,
        })),
      getTotalSize: () => count * size,
    };
  },
}));

vi.mock("@/components/charts/trade-frequency-chart", () => ({
  TradeFrequencyChart: () => <div data-testid="trade-frequency-chart" />,
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: () => <div />,
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
}));

const makeTrade = (overrides: Partial<TradeRecord> = {}): TradeRecord => ({
  date: "2024-03-01",
  type: "pac_execution",
  asset_id: "stocks",
  direction: "buy",
  amount_eur: 500,
  quantity: 10,
  price: 50,
  fee: 1,
  skipped: false,
  ...overrides,
});

const makeRun = (trades: TradeRecord[]): RunResult => ({
  run_id: "test-run",
  created_at: "2024-01-01T00:00:00Z",
  config: {
    strategy: "test",
    strategy_params: {},
    start_date: "2024-01-01",
    end_date: "2024-12-31",
    initial_cash: 10000,
    monthly_contribution: 500,
    pac_execution_days: [1],
    settlement_fee: 1,
    spread_bps: 10,
    slippage_days: [0, 2],
    monte_carlo_iterations: 100,
    metrics: [],
    benchmark: false,
  },
  monte_carlo: { iterations: 100, slippage_range: [0, 2] },
  metrics: {},
  equity_curve: [],
  allocations: [],
  trades,
  summary: {
    total_invested: 6000,
    final_value: { p5: 5000, median: 6000, p95: 7000 },
    total_fees: { p5: 10, median: 12, p95: 15 },
    total_trades: { p5: 10, median: 12, p95: 15 },
    total_pac_executions: 12,
  },
  signal_log: [],
  indicator_series: [],
  strategy_events: [],
  strategy_event_meta: [],
  benchmark_equity_curve: null,
});

describe("TradesTab", () => {
  it("renders trade data in virtual table", () => {
    const trades = [
      makeTrade({ asset_id: "stocks", direction: "buy", date: "2024-03-01" }),
      makeTrade({ asset_id: "bonds", direction: "sell", date: "2024-04-01" }),
    ];
    render(<TradesTab run={makeRun(trades)} />);
    expect(screen.getByText("stocks")).toBeInTheDocument();
    expect(screen.getByText("bonds")).toBeInTheDocument();
    expect(screen.getByText("2 trades")).toBeInTheDocument();
  });

  it("filters by type", async () => {
    const user = userEvent.setup();
    const trades = [
      makeTrade({ type: "pac_execution", asset_id: "stocks" }),
      makeTrade({ type: "hard_rebalance", asset_id: "bonds" }),
    ];
    render(<TradesTab run={makeRun(trades)} />);
    expect(screen.getByText("2 trades")).toBeInTheDocument();

    // Open the type filter select (first combobox)
    // Type filter is the first select
    await user.click(getTrigger(0));
    const pacOption = await screen.findByRole("option", { name: "PAC Execution" });
    await user.click(pacOption);

    expect(screen.getByText("1 of 2 trades")).toBeInTheDocument();
    expect(screen.getByText("stocks")).toBeInTheDocument();
    expect(screen.queryByText("bonds")).not.toBeInTheDocument();
  });

  it("filters by asset", async () => {
    const user = userEvent.setup();
    const trades = [
      makeTrade({ asset_id: "stocks" }),
      makeTrade({ asset_id: "bonds" }),
      makeTrade({ asset_id: "gold" }),
    ];
    render(<TradesTab run={makeRun(trades)} />);

    // Asset filter is the second select
    await user.click(getTrigger(1));
    const bondsOption = await screen.findByRole("option", { name: "bonds" });
    await user.click(bondsOption);

    expect(screen.getByText("1 of 3 trades")).toBeInTheDocument();
    // "bonds" appears in both the select trigger and the table row
    expect(screen.getAllByText("bonds").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("stocks")).not.toBeInTheDocument();
    expect(screen.queryByText("gold")).not.toBeInTheDocument();
  });

  it("filters by direction", async () => {
    const user = userEvent.setup();
    const trades = [
      makeTrade({ direction: "buy", asset_id: "stocks" }),
      makeTrade({ direction: "sell", asset_id: "bonds" }),
    ];
    render(<TradesTab run={makeRun(trades)} />);

    // Direction filter is the third select
    await user.click(getTrigger(2));
    const sellOption = await screen.findByRole("option", { name: "Sell" });
    await user.click(sellOption);

    expect(screen.getByText("1 of 2 trades")).toBeInTheDocument();
    expect(screen.getByText("bonds")).toBeInTheDocument();
  });

  it("applies row coloring via getRowClassName", () => {
    const trades = [
      makeTrade({ direction: "buy", skipped: false }),
      makeTrade({ direction: "sell", skipped: false }),
      makeTrade({ direction: "buy", skipped: true }),
    ];
    const { container } = render(<TradesTab run={makeRun(trades)} />);
    const rows = container.querySelectorAll("tbody tr");
    // buy → success, sell → danger, skipped → warning
    const buyRow = rows[0];
    const sellRow = rows[1];
    const skippedRow = rows[2];
    expect(buyRow?.className).toContain("bg-success");
    expect(sellRow?.className).toContain("bg-danger");
    expect(skippedRow?.className).toContain("bg-warning");
  });

  it("triggers CSV export on button click", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.fn();
    const createElementOrig = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = createElementOrig(tag);
      if (tag === "a") {
        el.click = clickSpy;
      }
      return el;
    });
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    const trades = [makeTrade()];
    render(<TradesTab run={makeRun(trades)} />);

    const exportBtn = screen.getByRole("button", { name: /export csv/i });
    await user.click(exportBtn);
    expect(clickSpy).toHaveBeenCalled();

    vi.restoreAllMocks();
  });

  it("shows empty state when no trades match filters", async () => {
    const user = userEvent.setup();
    const trades = [makeTrade({ type: "pac_execution" })];
    render(<TradesTab run={makeRun(trades)} />);

    await user.click(getTrigger(0));
    const rebalanceOption = await screen.findByRole("option", {
      name: "Hard Rebalance",
    });
    await user.click(rebalanceOption);

    expect(screen.getByText("No matching trades")).toBeInTheDocument();
  });
});
