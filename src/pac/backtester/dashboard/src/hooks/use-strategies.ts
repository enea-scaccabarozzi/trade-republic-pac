import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { StrategiesResponse } from "@/types/api";

export function useStrategies() {
  return useQuery({
    queryKey: ["strategies"],
    queryFn: () => apiFetch<StrategiesResponse>("/strategies"),
    staleTime: 5 * 60_000,
  });
}
