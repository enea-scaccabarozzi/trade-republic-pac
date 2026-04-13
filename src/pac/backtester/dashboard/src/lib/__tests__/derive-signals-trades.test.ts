import { describe, expect, it } from "vitest";
import type { SignalRecord, TradeRecord } from "@/types/api";
import { computeRuleStats, computeSignalAttribution, computeTradeFrequency } from "../derive";

const makeSignal = (overrides: Partial<SignalRecord> = {}): SignalRecord => ({
  date: "2024-03-01",
  rule_name: "equity_drawdown",
  severity: "warning",
  message: "Drawdown detected",
  metadata: {},
  ...overrides,
});

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

describe("computeSignalAttribution", () => {
  it("attributes signals to hard_rebalance trades on same date", () => {
    const trades = [makeTrade({ type: "hard_rebalance", date: "2024-03-01" })];
    const signals = [makeSignal({ date: "2024-03-01" })];
    const result = computeSignalAttribution(trades, signals);
    expect(result[0]?.attributedSignals).toHaveLength(1);
    expect(result[0]?.attributedSignals[0]?.rule_name).toBe("equity_drawdown");
  });

  it("returns empty attribution for hard_rebalance with no matching signals", () => {
    const trades = [makeTrade({ type: "hard_rebalance", date: "2024-03-01" })];
    const signals = [makeSignal({ date: "2024-04-01" })];
    const result = computeSignalAttribution(trades, signals);
    expect(result[0]?.attributedSignals).toEqual([]);
  });

  it("always returns empty attribution for pac_execution", () => {
    const trades = [makeTrade({ type: "pac_execution", date: "2024-03-01" })];
    const signals = [makeSignal({ date: "2024-03-01" })];
    const result = computeSignalAttribution(trades, signals);
    expect(result[0]?.attributedSignals).toEqual([]);
  });

  it("attributes multiple signals on same date", () => {
    const trades = [makeTrade({ type: "hard_rebalance", date: "2024-03-01" })];
    const signals = [
      makeSignal({ date: "2024-03-01", rule_name: "rule_a" }),
      makeSignal({ date: "2024-03-01", rule_name: "rule_b" }),
    ];
    const result = computeSignalAttribution(trades, signals);
    expect(result[0]?.attributedSignals).toHaveLength(2);
  });

  it("returns empty array for empty trades", () => {
    expect(computeSignalAttribution([], [makeSignal()])).toEqual([]);
  });

  it("gives empty attribution when signal log is empty", () => {
    const trades = [makeTrade({ type: "hard_rebalance" })];
    const result = computeSignalAttribution(trades, []);
    expect(result[0]?.attributedSignals).toEqual([]);
  });
});

describe("computeRuleStats", () => {
  it("computes stats for two rules", () => {
    const signals = [
      makeSignal({ rule_name: "rule_a", date: "2024-01-01" }),
      makeSignal({ rule_name: "rule_a", date: "2024-02-01" }),
      makeSignal({ rule_name: "rule_b", date: "2024-01-15" }),
    ];
    const result = computeRuleStats(signals, "2024-01-01", "2024-04-01");
    expect(result).toHaveLength(2);
    const ruleA = result.find((r) => r.ruleName === "rule_a");
    expect(ruleA?.triggerCount).toBe(2);
    const ruleB = result.find((r) => r.ruleName === "rule_b");
    expect(ruleB?.triggerCount).toBe(1);
  });

  it("computes severity breakdown", () => {
    const signals = [
      makeSignal({ severity: "warning" }),
      makeSignal({ severity: "warning" }),
      makeSignal({ severity: "critical" }),
    ];
    const result = computeRuleStats(signals, "2024-01-01", "2024-04-01");
    expect(result[0]?.severityBreakdown).toEqual({
      warning: 2,
      critical: 1,
    });
  });

  it("computes avgFrequencyDays for multiple signals", () => {
    const signals = [
      makeSignal({ date: "2024-01-01" }),
      makeSignal({ date: "2024-02-01" }),
      makeSignal({ date: "2024-03-01" }),
    ];
    // 90 days total, 3 signals → 90 / 2 = 45
    const result = computeRuleStats(signals, "2024-01-01", "2024-04-01");
    expect(result[0]?.avgFrequencyDays).toBeCloseTo(45.5, 0);
  });

  it("returns null avgFrequencyDays for single signal", () => {
    const signals = [makeSignal({ date: "2024-02-01" })];
    const result = computeRuleStats(signals, "2024-01-01", "2024-04-01");
    expect(result[0]?.avgFrequencyDays).toBeNull();
  });

  it("sets correct first and last trigger", () => {
    const signals = [
      makeSignal({ date: "2024-03-01" }),
      makeSignal({ date: "2024-01-01" }),
      makeSignal({ date: "2024-02-01" }),
    ];
    const result = computeRuleStats(signals, "2024-01-01", "2024-04-01");
    expect(result[0]?.firstTrigger).toBe("2024-01-01");
    expect(result[0]?.lastTrigger).toBe("2024-03-01");
  });
});

describe("computeTradeFrequency", () => {
  it("groups trades by month", () => {
    const trades = [
      makeTrade({ date: "2024-01-05", direction: "buy" }),
      makeTrade({ date: "2024-01-15", direction: "sell" }),
      makeTrade({ date: "2024-02-10", direction: "buy" }),
    ];
    const result = computeTradeFrequency(trades);
    expect(result).toHaveLength(2);
    expect(result[0]?.month).toBe("2024-01");
    expect(result[0]?.buy).toBe(1);
    expect(result[0]?.sell).toBe(1);
    expect(result[0]?.total).toBe(2);
    expect(result[1]?.month).toBe("2024-02");
    expect(result[1]?.buy).toBe(1);
  });

  it("counts skipped trades", () => {
    const trades = [
      makeTrade({ date: "2024-01-05", skipped: true }),
      makeTrade({ date: "2024-01-15", direction: "buy" }),
    ];
    const result = computeTradeFrequency(trades);
    expect(result[0]?.skipped).toBe(1);
    expect(result[0]?.buy).toBe(1);
    expect(result[0]?.total).toBe(2);
  });

  it("sorts chronologically", () => {
    const trades = [makeTrade({ date: "2024-03-01" }), makeTrade({ date: "2024-01-01" })];
    const result = computeTradeFrequency(trades);
    expect(result[0]?.month).toBe("2024-01");
    expect(result[1]?.month).toBe("2024-03");
  });

  it("returns empty for no trades", () => {
    expect(computeTradeFrequency([])).toEqual([]);
  });

  it("handles single trade", () => {
    const result = computeTradeFrequency([makeTrade({ date: "2024-06-15" })]);
    expect(result).toHaveLength(1);
    expect(result[0]?.total).toBe(1);
  });
});
