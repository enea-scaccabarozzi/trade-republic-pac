import { describe, expect, it } from "vitest";
import type { AllocationPoint, EquityCurvePoint } from "@/types/api";
import { computeDrawdownCurve, flattenAllocations, METRIC_DISPLAY_MAP } from "../derive";

describe("computeDrawdownCurve", () => {
  it("returns empty array for empty input", () => {
    expect(computeDrawdownCurve([])).toEqual([]);
  });

  it("returns 0 drawdown for single point", () => {
    const input: EquityCurvePoint[] = [{ date: "2024-01-01", p5: 900, median: 1000, p95: 1100 }];
    const result = computeDrawdownCurve(input);
    expect(result).toEqual([{ date: "2024-01-01", drawdown: 0 }]);
  });

  it("returns all zeros for monotonically increasing equity", () => {
    const input: EquityCurvePoint[] = [
      { date: "2024-01-01", p5: 900, median: 1000, p95: 1100 },
      { date: "2024-02-01", p5: 950, median: 1100, p95: 1200 },
      { date: "2024-03-01", p5: 1000, median: 1200, p95: 1300 },
    ];
    const result = computeDrawdownCurve(input);
    expect(result.every((p) => p.drawdown === 0)).toBe(true);
  });

  it("computes correct drawdown for declining equity", () => {
    const input: EquityCurvePoint[] = [
      { date: "2024-01-01", p5: 0, median: 1000, p95: 0 },
      { date: "2024-02-01", p5: 0, median: 1200, p95: 0 },
      { date: "2024-03-01", p5: 0, median: 900, p95: 0 },
      { date: "2024-04-01", p5: 0, median: 1100, p95: 0 },
    ];
    const result = computeDrawdownCurve(input);
    expect(result[0]?.drawdown).toBe(0);
    expect(result[1]?.drawdown).toBe(0);
    // 900 from peak of 1200 = -25%
    expect(result[2]?.drawdown).toBeCloseTo(-0.25);
    // 1100 from peak of 1200 = -8.33%
    expect(result[3]?.drawdown).toBeCloseTo(-1 / 12);
  });
});

describe("flattenAllocations", () => {
  it("returns empty for empty input", () => {
    const result = flattenAllocations([]);
    expect(result).toEqual({ data: [], assetIds: [] });
  });

  it("flattens allocations correctly", () => {
    const input: AllocationPoint[] = [
      {
        date: "2024-01-01",
        assets: {
          stocks: { p5: 0.6, median: 0.7, p95: 0.8 },
          bonds: { p5: 0.1, median: 0.15, p95: 0.2 },
          gold: { p5: 0.1, median: 0.15, p95: 0.2 },
        },
      },
      {
        date: "2024-02-01",
        assets: {
          stocks: { p5: 0.55, median: 0.65, p95: 0.75 },
          bonds: { p5: 0.12, median: 0.18, p95: 0.25 },
          gold: { p5: 0.12, median: 0.17, p95: 0.22 },
        },
      },
    ];
    const result = flattenAllocations(input);

    expect(result.assetIds).toEqual(["stocks", "bonds", "gold"]);
    expect(result.data).toHaveLength(2);
    expect(result.data[0]).toEqual({
      date: "2024-01-01",
      stocks: 0.7,
      bonds: 0.15,
      gold: 0.15,
    });
    expect(result.data[1]).toEqual({
      date: "2024-02-01",
      stocks: 0.65,
      bonds: 0.18,
      gold: 0.17,
    });
  });
});

describe("METRIC_DISPLAY_MAP", () => {
  it("has entries for all valid metrics", () => {
    const expectedKeys = ["cagr", "sharpe", "sortino", "calmar", "max_drawdown", "volatility"];
    for (const key of expectedKeys) {
      expect(METRIC_DISPLAY_MAP[key]).toBeDefined();
    }
  });

  it("has invertColor true for max_drawdown and volatility", () => {
    expect(METRIC_DISPLAY_MAP.max_drawdown?.invertColor).toBe(true);
    expect(METRIC_DISPLAY_MAP.volatility?.invertColor).toBe(true);
  });

  it("has invertColor false for positive metrics", () => {
    expect(METRIC_DISPLAY_MAP.cagr?.invertColor).toBe(false);
    expect(METRIC_DISPLAY_MAP.sharpe?.invertColor).toBe(false);
    expect(METRIC_DISPLAY_MAP.sortino?.invertColor).toBe(false);
    expect(METRIC_DISPLAY_MAP.calmar?.invertColor).toBe(false);
  });
});
