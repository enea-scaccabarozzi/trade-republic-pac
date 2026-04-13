import { describe, expect, it } from "vitest";
import { assignRunColors } from "../run-colors";

function fakeRun(id: string, strategy = "test") {
  return { run_id: id, config: { strategy } };
}

describe("assignRunColors", () => {
  it("assigns unique colors to each run", () => {
    const runs = [fakeRun("aaa"), fakeRun("bbb"), fakeRun("ccc")];
    const result = assignRunColors(runs);

    expect(result).toHaveLength(3);
    const colors = new Set(result.map((r) => r.color));
    expect(colors.size).toBe(3);
  });

  it("builds label from strategy and truncated run id", () => {
    const runs = [fakeRun("abcdef12-long-id", "crisis_exploit")];
    const result = assignRunColors(runs);

    expect(result[0]?.label).toBe("crisis_exploit (abcdef12)");
  });

  it("caps at 8 runs when given more", () => {
    const runs = Array.from({ length: 12 }, (_, i) => fakeRun(`run-${i}`));
    const result = assignRunColors(runs);

    expect(result).toHaveLength(8);
  });

  it("returns consistent colors for same position", () => {
    const runs1 = [fakeRun("aaa"), fakeRun("bbb")];
    const runs2 = [fakeRun("xxx"), fakeRun("yyy")];
    const result1 = assignRunColors(runs1);
    const result2 = assignRunColors(runs2);

    expect(result1[0]?.color).toBe(result2[0]?.color);
    expect(result1[1]?.color).toBe(result2[1]?.color);
  });

  it("returns empty array for empty input", () => {
    expect(assignRunColors([])).toEqual([]);
  });
});
