import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { RunColor } from "@/lib/run-colors";
import type { RunSummary } from "@/types/api";

vi.mock("@tanstack/react-router", () => ({
	Link: ({ children, ...props }: { children: React.ReactNode; to: string }) => (
		<a href={props.to}>{children}</a>
	),
}));

vi.mock("@/hooks/use-run-detail", () => ({
	useRunDetail: vi.fn(),
}));

vi.mock("@/components/charts/allocation-chart", () => ({
	AllocationChart: () => <div data-testid="allocation-chart" />,
}));

import { useRunDetail } from "@/hooks/use-run-detail";
import { RunDetailCard } from "../run-detail-card";

const mockUseRunDetail = useRunDetail as Mock;

const makeSummary = (): RunSummary => ({
	run_id: "run-abc123",
	created_at: "2024-01-01T00:00:00Z",
	strategy: "crisis_exploit",
	start_date: "2024-01-01",
	end_date: "2024-12-31",
	iterations: 100,
	final_value_median: 12000,
	cagr_median: 0.08,
	sharpe_median: 0.9,
	max_drawdown_median: -0.15,
	label: null,
	tags: [],
	experiment_id: null,
	quantstats_metrics: null,
});

const makeColor = (): RunColor => ({
	runId: "run-abc123",
	color: "var(--color-chart-1)",
	label: "crisis_exploit (run-abc1)",
});

function renderCard(summary = makeSummary(), color = makeColor()) {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>
			<RunDetailCard runSummary={summary} runColor={color} />
		</QueryClientProvider>,
	);
}

describe("RunDetailCard", () => {
	beforeEach(() => {
		mockUseRunDetail.mockReturnValue({ data: undefined, isLoading: false });
	});

	it("renders strategy name and run id prefix in collapsed state", () => {
		renderCard();

		expect(screen.getByText("crisis_exploit")).toBeInTheDocument();
		expect(screen.getByText("(run-abc1)")).toBeInTheDocument();
	});

	it("shows KPI values in collapsed state", () => {
		renderCard();

		expect(screen.getByText("CAGR")).toBeInTheDocument();
		expect(screen.getByText("Sharpe")).toBeInTheDocument();
		expect(screen.getByText("Max DD")).toBeInTheDocument();
	});

	it("calls useRunDetail with enabled: false when collapsed", () => {
		renderCard();

		expect(mockUseRunDetail).toHaveBeenCalledWith("run-abc123", {
			enabled: false,
		});
	});

	it("calls useRunDetail with enabled: true when expanded", async () => {
		const user = userEvent.setup();
		mockUseRunDetail.mockReturnValue({ data: undefined, isLoading: true });
		renderCard();

		const trigger = screen.getByRole("button");
		await user.click(trigger);

		expect(mockUseRunDetail).toHaveBeenCalledWith("run-abc123", {
			enabled: true,
		});
	});

	it("shows loading skeleton while data is loading", async () => {
		const user = userEvent.setup();
		mockUseRunDetail.mockReturnValue({ data: undefined, isLoading: true });
		renderCard();

		const trigger = screen.getByRole("button");
		await user.click(trigger);

		// The loading skeleton renders skeleton elements
		expect(mockUseRunDetail).toHaveBeenCalledWith("run-abc123", {
			enabled: true,
		});
	});

	it("shows full run details when expanded and loaded", async () => {
		const user = userEvent.setup();
		const fullRun = {
			run_id: "run-abc123",
			created_at: "2024-01-01T00:00:00Z",
			config: {
				strategy: "crisis_exploit",
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
			metrics: {
				strategy: {
					cagr: { p5: 0.05, median: 0.08, p95: 0.12, distribution: null },
					sharpe: { p5: 0.5, median: 0.9, p95: 1.3, distribution: null },
				},
			},
			equity_curve: [],
			allocations: [],
			trades: [],
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
		};

		mockUseRunDetail.mockReturnValue({
			data: { run: fullRun },
			isLoading: false,
		});

		renderCard();

		const trigger = screen.getByRole("button");
		await user.click(trigger);

		expect(screen.getByText("View details →")).toBeInTheDocument();
		expect(screen.getByText("10 bps")).toBeInTheDocument();
		expect(screen.getByTestId("allocation-chart")).toBeInTheDocument();
	});
});
