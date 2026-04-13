import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ProgressState } from "@/hooks/use-run-progress";
import { ProgressView } from "../progress-view";

describe("ProgressView", () => {
  const onComplete = vi.fn();
  const onError = vi.fn();

  it("shows progress bar with correct percentage text", () => {
    const progress: ProgressState = {
      current: 50,
      total: 100,
      status: "running",
      runId: null,
      error: null,
    };
    render(<ProgressView progress={progress} onComplete={onComplete} onError={onError} />);
    expect(screen.getByText("50 / 100")).toBeInTheDocument();
    expect(screen.getByText("Running Backtest...")).toBeInTheDocument();
  });

  it("shows elapsed and ETA fields while running", () => {
    const progress: ProgressState = {
      current: 10,
      total: 100,
      status: "running",
      runId: null,
      error: null,
    };
    render(<ProgressView progress={progress} onComplete={onComplete} onError={onError} />);
    expect(screen.getByText("Elapsed")).toBeInTheDocument();
    expect(screen.getByText("ETA")).toBeInTheDocument();
    expect(screen.getByText("Iterations")).toBeInTheDocument();
  });

  it("shows completion state", () => {
    const progress: ProgressState = {
      current: 100,
      total: 100,
      status: "completed",
      runId: "run-123",
      error: null,
    };
    render(<ProgressView progress={progress} onComplete={onComplete} onError={onError} />);
    expect(screen.getByText("Backtest Complete!")).toBeInTheDocument();
    expect(screen.getByText("Redirecting to results...")).toBeInTheDocument();
  });

  it("shows error state with retry button", async () => {
    const user = userEvent.setup();
    const handleError = vi.fn();
    const progress: ProgressState = {
      current: 30,
      total: 100,
      status: "failed",
      runId: null,
      error: "Connection lost",
    };
    render(<ProgressView progress={progress} onComplete={onComplete} onError={handleError} />);
    expect(screen.getByText("Backtest Failed")).toBeInTheDocument();
    expect(screen.getByText("Connection lost")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Try Again/i }));
    expect(handleError).toHaveBeenCalledOnce();
  });

  it("shows default error message when error string is null", () => {
    const progress: ProgressState = {
      current: 0,
      total: 100,
      status: "failed",
      runId: null,
      error: null,
    };
    render(<ProgressView progress={progress} onComplete={onComplete} onError={onError} />);
    expect(screen.getByText("An unexpected error occurred.")).toBeInTheDocument();
  });
});
