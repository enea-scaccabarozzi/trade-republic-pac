import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QuantstatsTab } from "../quantstats-tab";

vi.mock("@/hooks/use-research", () => ({
	useRunQuantstats: vi
		.fn()
		.mockReturnValue({ data: undefined, isPending: false }),
}));

describe("QuantstatsTab", () => {
	it("renders metrics table when metrics available", () => {
		render(
			<QuantstatsTab
				runId="run-1"
				metrics={{ cagr: 0.0812, sharpe: 1.234 }}
				reportPath={null}
			/>,
		);
		expect(screen.getByText("cagr")).toBeInTheDocument();
		expect(screen.getByText("sharpe")).toBeInTheDocument();
		expect(screen.getByText("0.0812")).toBeInTheDocument();
		expect(screen.getByText("1.2340")).toBeInTheDocument();
	});

	it("shows 'View Full Report' when report path exists", () => {
		render(
			<QuantstatsTab
				runId="run-1"
				metrics={null}
				reportPath="reports/quantstats.html"
			/>,
		);
		expect(screen.getByText("View Full Report")).toBeInTheDocument();
	});
});
