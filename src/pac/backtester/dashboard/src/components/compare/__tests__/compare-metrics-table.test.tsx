import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RunColor } from "@/lib/run-colors";
import type { MetricValue, RunResult } from "@/types/api";
import { CompareMetricsTable } from "../compare-metrics-table";

const makeMetrics = (
	overrides: Partial<Record<string, MetricValue>> = {},
): Record<string, Record<string, MetricValue>> => ({
	strategy: {
		cagr: { p5: 0.05, median: 0.08, p95: 0.12, distribution: null },
		sharpe: { p5: 0.5, median: 0.9, p95: 1.3, distribution: null },
		sortino: { p5: 0.7, median: 1.2, p95: 1.8, distribution: null },
		calmar: { p5: 0.3, median: 0.6, p95: 1.0, distribution: null },
		max_drawdown: { p5: -0.25, median: -0.15, p95: -0.08, distribution: null },
		volatility: { p5: 0.1, median: 0.14, p95: 0.18, distribution: null },
		...overrides,
	},
});

const makeRun = (
	id: string,
	strategy: string,
	metrics = makeMetrics(),
): RunResult => ({
	run_id: id,
	created_at: "2024-01-01T00:00:00Z",
	config: {
		strategy,
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
	metrics,
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
	label: null,
	tags: [],
	experiment_id: null,
	quantstats_report_path: null,
	quantstats_metrics: null,
	oos_metadata: null,
});

const singleColor: RunColor = {
	runId: "run-a",
	color: "var(--color-chart-1)",
	label: "Strategy A",
};

const runColors: RunColor[] = [
	singleColor,
	{ runId: "run-b", color: "var(--color-chart-2)", label: "Strategy B" },
];

describe("CompareMetricsTable", () => {
	it("renders a row for each metric", () => {
		const runs = [
			makeRun("run-a", "Strategy A"),
			makeRun("run-b", "Strategy B"),
		];
		render(<CompareMetricsTable runs={runs} runColors={runColors} />);

		expect(screen.getByText("CAGR")).toBeInTheDocument();
		expect(screen.getByText("Sharpe Ratio")).toBeInTheDocument();
		expect(screen.getByText("Sortino Ratio")).toBeInTheDocument();
		expect(screen.getByText("Calmar Ratio")).toBeInTheDocument();
		expect(screen.getByText("Max Drawdown")).toBeInTheDocument();
		expect(screen.getByText("Volatility")).toBeInTheDocument();
	});

	it("highlights best value with 'Best' badge", () => {
		const betterMetrics = makeMetrics({
			cagr: { p5: 0.08, median: 0.12, p95: 0.16, distribution: null },
		});
		const runs = [
			makeRun("run-a", "Strategy A", betterMetrics),
			makeRun("run-b", "Strategy B"),
		];
		render(<CompareMetricsTable runs={runs} runColors={runColors} />);

		const bestBadges = screen.getAllByText("Best");
		expect(bestBadges.length).toBeGreaterThanOrEqual(1);
	});

	it("shows win count row", () => {
		const runs = [
			makeRun("run-a", "Strategy A"),
			makeRun("run-b", "Strategy B"),
		];
		render(<CompareMetricsTable runs={runs} runColors={runColors} />);

		expect(screen.getByText("Win Count")).toBeInTheDocument();
	});

	it("handles single run", () => {
		const runs = [makeRun("run-a", "Strategy A")];
		render(<CompareMetricsTable runs={runs} runColors={[singleColor]} />);

		expect(screen.getByText("CAGR")).toBeInTheDocument();
		expect(screen.getByText("Win Count")).toBeInTheDocument();
	});

	it("renders column header with run label", () => {
		const runs = [makeRun("run-a", "Strategy A")];
		render(<CompareMetricsTable runs={runs} runColors={[singleColor]} />);

		expect(screen.getByText("Strategy A")).toBeInTheDocument();
	});
});
