import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
	afterEach,
	beforeEach,
	describe,
	expect,
	it,
	type Mock,
	vi,
} from "vitest";
import type { ExperimentDetailResponse, ExperimentSummary } from "@/types/api";

vi.mock("@tanstack/react-router", () => ({
	createFileRoute: () => {
		const route = (opts: Record<string, unknown>) => ({
			...opts,
			useParams: () => ({ id: "exp-001" }),
		});
		return route;
	},
	Link: ({ children, ...props }: { children: React.ReactNode; to: string }) => (
		<a href={props.to}>{children}</a>
	),
	useNavigate: () => vi.fn(),
}));

vi.mock("@/hooks/use-research", () => ({
	useExperiments: vi.fn(),
	useExperiment: vi.fn(),
}));

vi.mock("@/components/research/experiment-runs", () => ({
	ExperimentRuns: ({ runIds }: { runIds: string[] }) => (
		<div data-testid="experiment-runs">
			{runIds.map((id) => (
				<span key={id}>{id}</span>
			))}
		</div>
	),
}));

vi.mock("@/components/research/artifact-viewer", () => ({
	ArtifactViewer: () => <div data-testid="artifact-viewer" />,
}));

vi.mock("@/components/research/report-viewer-dialog", () => ({
	ReportViewerDialog: () => null,
}));

import { useExperiment, useExperiments } from "@/hooks/use-research";
import { ResearchIndex } from "../research.index";
import { ExperimentDetail } from "../research.$id";

const mockUseExperiments = useExperiments as Mock;
const mockUseExperiment = useExperiment as Mock;

function makeExperiment(
	overrides: Partial<ExperimentSummary> = {},
): ExperimentSummary {
	return {
		id: "exp-001",
		slug: "test-experiment",
		title: "Test Experiment",
		status: "exploring",
		strategy_name: "crisis_exploit",
		tags: ["v1", "research"],
		created: "2026-04-01T12:00:00Z",
		concluded: null,
		artifact_count: 3,
		report_count: 1,
		result_file_count: 2,
		...overrides,
	};
}

function renderWithProviders() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>
			<ResearchIndex />
		</QueryClientProvider>,
	);
}

describe("ResearchIndex", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders skeleton during loading", () => {
		mockUseExperiments.mockReturnValue({
			data: undefined,
			isPending: true,
			isError: false,
		});
		const { container } = renderWithProviders();
		const skeletons = container.querySelectorAll("[data-slot='skeleton']");
		expect(skeletons.length).toBeGreaterThan(0);
	});

	it("renders error state", () => {
		mockUseExperiments.mockReturnValue({
			data: undefined,
			isPending: false,
			isError: true,
		});
		renderWithProviders();
		expect(screen.getByText(/failed to load experiments/i)).toBeInTheDocument();
	});

	it("renders empty state when no experiments", () => {
		mockUseExperiments.mockReturnValue({
			data: { experiments: [], total: 0 },
			isPending: false,
			isError: false,
		});
		renderWithProviders();
		expect(screen.getByText("No experiments found")).toBeInTheDocument();
	});

	it("renders experiment list from API", () => {
		mockUseExperiments.mockReturnValue({
			data: {
				experiments: [
					makeExperiment(),
					makeExperiment({
						id: "exp-002",
						slug: "another",
						title: "Another Experiment",
						status: "validated",
					}),
				],
				total: 2,
			},
			isPending: false,
			isError: false,
		});
		renderWithProviders();
		expect(screen.getByText("Test Experiment")).toBeInTheDocument();
		expect(screen.getByText("Another Experiment")).toBeInTheDocument();
		expect(screen.getByText("Exploring")).toBeInTheDocument();
		expect(screen.getByText("Validated")).toBeInTheDocument();
	});

	it("renders tags as badges", () => {
		mockUseExperiments.mockReturnValue({
			data: {
				experiments: [makeExperiment({ tags: ["alpha", "beta"] })],
				total: 1,
			},
			isPending: false,
			isError: false,
		});
		renderWithProviders();
		expect(screen.getByText("alpha")).toBeInTheDocument();
		expect(screen.getByText("beta")).toBeInTheDocument();
	});
});

function makeExperimentDetail(
	overrides: Partial<ExperimentDetailResponse> = {},
): ExperimentDetailResponse {
	return {
		id: "exp-001",
		slug: "test-experiment",
		title: "Test Experiment",
		hypothesis: "Testing whether this works",
		status: "exploring",
		strategy_name: "crisis_exploit",
		strategy_params_file: null,
		tags: ["v1"],
		created: "2026-04-01T12:00:00Z",
		concluded: null,
		artifacts: [],
		reports: [],
		result_files: [],
		linked_run_ids: [],
		readme_html: null,
		...overrides,
	};
}

function renderDetailWithProviders() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>
			<ExperimentDetail />
		</QueryClientProvider>,
	);
}

describe("ExperimentDetail", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it("renders header with title, status badge, date", () => {
		mockUseExperiment.mockReturnValue({
			data: makeExperimentDetail(),
			isPending: false,
			isError: false,
		});
		renderDetailWithProviders();
		expect(screen.getByText("Test Experiment")).toBeInTheDocument();
		expect(screen.getByText("Exploring")).toBeInTheDocument();
		expect(screen.getByText(/Apr/)).toBeInTheDocument();
	});

	it("renders hypothesis text", () => {
		mockUseExperiment.mockReturnValue({
			data: makeExperimentDetail({ hypothesis: "Markets are inefficient" }),
			isPending: false,
			isError: false,
		});
		renderDetailWithProviders();
		expect(screen.getByText("Markets are inefficient")).toBeInTheDocument();
	});

	it("Overview tab shows rendered README", () => {
		mockUseExperiment.mockReturnValue({
			data: makeExperimentDetail({
				readme_html: "<p>Experiment overview content</p>",
			}),
			isPending: false,
			isError: false,
		});
		renderDetailWithProviders();
		expect(screen.getByText("Experiment overview content")).toBeInTheDocument();
	});

	it("Runs tab lists linked runs", async () => {
		mockUseExperiment.mockReturnValue({
			data: makeExperimentDetail({
				linked_run_ids: ["run-a", "run-b"],
			}),
			isPending: false,
			isError: false,
		});
		renderDetailWithProviders();
		const user = userEvent.setup();
		const runsTab = screen.getByRole("tab", { name: /Runs/ });
		await user.click(runsTab);
		expect(screen.getByText("run-a")).toBeInTheDocument();
		expect(screen.getByText("run-b")).toBeInTheDocument();
	});
});
