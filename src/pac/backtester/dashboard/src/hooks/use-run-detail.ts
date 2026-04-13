import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { RUN_STALE_TIME } from "@/lib/query-config";
import type { RunDetailResponse } from "@/types/api";

export function useRunDetail(runId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["runs", runId],
    queryFn: () => apiFetch<RunDetailResponse>(`/runs/${runId}`),
    enabled: (options?.enabled ?? true) && !!runId,
    staleTime: RUN_STALE_TIME,
  });
}
