import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReportViewerDialog } from "../report-viewer-dialog";

describe("ReportViewerDialog", () => {
	it("renders dialog with title when open", () => {
		render(
			<ReportViewerDialog
				experimentId="exp-1"
				reportPath="reports/quantstats.html"
				open={true}
				onOpenChange={() => {}}
			/>,
		);
		expect(screen.getByText("quantstats.html")).toBeInTheDocument();
	});

	it("renders iframe with sandbox attribute", () => {
		const { container } = render(
			<ReportViewerDialog
				experimentId="exp-1"
				reportPath="reports/quantstats.html"
				open={true}
				onOpenChange={() => {}}
			/>,
		);
		const iframe = container.querySelector("iframe");
		expect(iframe).toBeTruthy();
		expect(iframe?.getAttribute("sandbox")).toBe("allow-same-origin");
	});

	it("does not render iframe when closed", () => {
		const { container } = render(
			<ReportViewerDialog
				experimentId="exp-1"
				reportPath="reports/quantstats.html"
				open={false}
				onOpenChange={() => {}}
			/>,
		);
		const iframe = container.querySelector("iframe");
		expect(iframe).toBeNull();
	});

	it("iframe src points to the correct API path", () => {
		const { container } = render(
			<ReportViewerDialog
				experimentId="exp-1"
				reportPath="reports/quantstats.html"
				open={true}
				onOpenChange={() => {}}
			/>,
		);
		const iframe = container.querySelector("iframe");
		expect(iframe?.getAttribute("src")).toBe(
			"/api/research/experiments/exp-1/files/reports/quantstats.html",
		);
	});
});
