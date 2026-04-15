import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { OOSMetadata } from "@/types/api";
import { OOSTab } from "../oos-tab";

const baseMetadata: OOSMetadata = {
	method: "holdout",
	holdout_date: "2025-01-01",
	walk_forward_windows: null,
	event_calendar: null,
	degradation_ratio: 1.2,
};

describe("OOSTab", () => {
	it("renders method badge", () => {
		render(<OOSTab metadata={baseMetadata} />);
		expect(screen.getByText("Temporal Holdout")).toBeInTheDocument();
	});

	it("renders degradation ratio with correct color for moderate value", () => {
		render(<OOSTab metadata={{ ...baseMetadata, degradation_ratio: 1.2 }} />);
		const badge = screen.getByText("1.20x");
		expect(badge).toBeInTheDocument();
		expect(badge.className).toContain("yellow");
	});

	it("renders degradation ratio with green for low value", () => {
		render(<OOSTab metadata={{ ...baseMetadata, degradation_ratio: 0.8 }} />);
		const badge = screen.getByText("0.80x");
		expect(badge.className).toContain("green");
	});

	it("renders degradation ratio with red for high value", () => {
		render(<OOSTab metadata={{ ...baseMetadata, degradation_ratio: 2.0 }} />);
		const badge = screen.getByText("2.00x");
		expect(badge.className).toContain("red");
	});
});
