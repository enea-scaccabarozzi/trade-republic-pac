import { useQueries } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { RUN_STALE_TIME } from "@/lib/query-config";
import type { RunDetailResponse, RunResult } from "@/types/api";

export interface CompareRunsResult {
  /** Successfully loaded runs, in the same order as input IDs. */
  runs: RunResult[];
  /** Whether any run is still loading. */
  isLoading: boolean;
  /** Per-run error states indexed by run ID. */
  errors: Record<string, Error>;
  /** Whether all runs have loaded successfully. */
  isComplete: boolean;
}

export function useCompareRuns(runIds: string[]): CompareRunsResult {
  const results = useQueries({
    queries: runIds.map((id) => ({
      queryKey: ["runs", id],
      queryFn: () => apiFetch<RunDetailResponse>(`/runs/${id}`),
      enabled: !!id,
      staleTime: RUN_STALE_TIME,
    })),
  });

  const runs: RunResult[] = [];
  const errors: Record<string, Error> = {};
  let isLoading = false;

  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    const runId = runIds[i];
    if (!result || !runId) continue;
    if (result.isLoading) isLoading = true;
    if (result.error) errors[runId] = result.error as Error;
    if (result.data) runs.push(result.data.run);
  }

  return {
    runs,
    isLoading,
    errors,
    isComplete: runs.length === runIds.length && !isLoading,
  };
}
