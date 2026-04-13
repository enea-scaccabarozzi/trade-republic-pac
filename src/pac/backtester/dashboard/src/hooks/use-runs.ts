import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { RunListResponse } from "@/types/api";

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => apiFetch<RunListResponse>("/runs"),
  });
}

export function useDeleteRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => apiFetch(`/runs/${runId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useDeleteRuns() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (runIds: string[]) => {
      for (const id of runIds) {
        await apiFetch(`/runs/${id}`, { method: "DELETE" });
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["runs"] }),
  });
}
