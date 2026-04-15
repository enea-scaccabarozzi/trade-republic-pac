import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "../status-badge";

describe("StatusBadge", () => {
	it("renders correct label for exploring status", () => {
		render(<StatusBadge status="exploring" />);
		expect(screen.getByText("Exploring")).toBeInTheDocument();
	});

	it("renders correct label for validated status", () => {
		render(<StatusBadge status="validated" />);
		expect(screen.getByText("Validated")).toBeInTheDocument();
	});

	it("renders correct label for rejected status", () => {
		render(<StatusBadge status="rejected" />);
		expect(screen.getByText("Rejected")).toBeInTheDocument();
	});

	it("renders correct label for published status", () => {
		render(<StatusBadge status="published" />);
		expect(screen.getByText("Published")).toBeInTheDocument();
	});

	it("renders raw status string for unknown status", () => {
		render(<StatusBadge status="custom_status" />);
		expect(screen.getByText("custom_status")).toBeInTheDocument();
	});

	it("renders as a badge element", () => {
		render(<StatusBadge status="exploring" />);
		const badge = screen.getByText("Exploring");
		expect(badge).toHaveAttribute("data-slot", "badge");
	});
});
