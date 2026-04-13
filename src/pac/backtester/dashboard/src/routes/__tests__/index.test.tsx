import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { RunSummary } from "@/types/api";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (opts: Record<string, unknown>) => opts,
  Link: ({ children, ...props }: { children: React.ReactNode; to: string }) => (
    <a href={props.to}>{children}</a>
  ),
  useNavigate: () => vi.fn(),
}));

vi.mock("@/hooks/use-runs", () => ({
  useRuns: vi.fn(),
  useDeleteRuns: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}));

import { useDeleteRuns, useRuns } from "@/hooks/use-runs";
import { DashboardHome } from "../index";

const mockUseRuns = useRuns as Mock;
const mockUseDeleteRuns = useDeleteRuns as Mock;

function makeRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    created_at: "2025-06-01T12:00:00Z",
    strategy: "crisis_exploit",
    start_date: "2020-01-01",
    end_date: "2025-01-01",
    iterations: 100,
    final_value_median: 15000,
    cagr_median: 0.08,
    sharpe_median: 1.2,
    max_drawdown_median: -0.15,
    ...overrides,
  };
}

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardHome />
    </QueryClientProvider>,
  );
}

describe("DashboardHome", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDeleteRuns.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    });
  });

  it("renders skeleton elements during loading", () => {
    mockUseRuns.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = renderWithProviders();
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error message with retry button", () => {
    mockUseRuns.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("Network failure"),
      refetch: vi.fn(),
    });
    renderWithProviders();
    expect(screen.getByText(/failed to load runs/i)).toBeInTheDocument();
    expect(screen.getByText(/network failure/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders empty state when runs array is empty", () => {
    mockUseRuns.mockReturnValue({
      data: { runs: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders();
    expect(screen.getByText("No backtests yet")).toBeInTheDocument();
  });

  it("renders summary bar and table with strategy names when data present", () => {
    const runs: RunSummary[] = [
      makeRun({ run_id: "r1", strategy: "alpha" }),
      makeRun({ run_id: "r2", strategy: "beta" }),
    ];
    mockUseRuns.mockReturnValue({
      data: { runs, total: 2 },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders();
    expect(screen.getAllByText("alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByText("beta").length).toBeGreaterThan(0);
  });

  it("filters rows when searching by strategy name", async () => {
    const user = userEvent.setup();
    const runs: RunSummary[] = [
      makeRun({ run_id: "r1", strategy: "alpha_strat" }),
      makeRun({ run_id: "r2", strategy: "beta_strat" }),
    ];
    mockUseRuns.mockReturnValue({
      data: { runs, total: 2 },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders();

    const searchInput = screen.getByPlaceholderText(/search strategies/i);
    await user.type(searchInput, "alpha");

    expect(screen.getAllByText("alpha_strat").length).toBeGreaterThan(0);
    expect(screen.queryByText("beta_strat")).not.toBeInTheDocument();
  });
});
