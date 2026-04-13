import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RunColor } from "@/lib/run-colors";
import { RunColorLegend } from "../run-color-legend";

const colors: RunColor[] = [
  {
    runId: "run-1",
    color: "var(--color-chart-1)",
    label: "Strategy A (run-1aaa)",
  },
  {
    runId: "run-2",
    color: "var(--color-chart-2)",
    label: "Strategy B (run-2bbb)",
  },
];

describe("RunColorLegend", () => {
  it("renders a label for each run color", () => {
    render(<RunColorLegend runColors={colors} />);

    expect(screen.getByText("Strategy A (run-1aaa)")).toBeInTheDocument();
    expect(screen.getByText("Strategy B (run-2bbb)")).toBeInTheDocument();
  });

  it("renders a colored dot for each entry", () => {
    const { container } = render(<RunColorLegend runColors={colors} />);

    const dots = container.querySelectorAll("span.rounded-full");
    expect(dots).toHaveLength(2);
  });

  it("renders nothing when given empty array", () => {
    const { container } = render(<RunColorLegend runColors={[]} />);

    const items = container.querySelectorAll("span.rounded-full");
    expect(items).toHaveLength(0);
  });
});
