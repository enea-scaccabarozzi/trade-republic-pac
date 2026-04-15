import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
	ExperimentDetailResponse,
	ExperimentListResponse,
	OOSMetadata,
	PaperListResponse,
	StrategySnapshotListResponse,
} from "@/types/api";

export function useExperiments(filters?: {
	status?: string;
	tag?: string;
	strategy?: string;
}) {
	const params = new URLSearchParams();
	if (filters?.status) params.set("status", filters.status);
	if (filters?.tag) params.set("tag", filters.tag);
	if (filters?.strategy) params.set("strategy", filters.strategy);
	const qs = params.toString();

	return useQuery({
		queryKey: ["research", "experiments", filters],
		queryFn: () =>
			apiFetch<ExperimentListResponse>(
				`/research/experiments${qs ? `?${qs}` : ""}`,
			),
	});
}

export function useExperiment(experimentId: string) {
	return useQuery({
		queryKey: ["research", "experiments", experimentId],
		queryFn: () =>
			apiFetch<ExperimentDetailResponse>(
				`/research/experiments/${experimentId}`,
			),
		enabled: !!experimentId,
	});
}

// Raw `fetch()` used here because `apiFetch` always parses JSON;
// these endpoints return binary/text content.
export function useExperimentFile(
	experimentId: string,
	filePath: string,
	options?: { raw?: boolean },
) {
	const raw = options?.raw ?? false;
	return useQuery({
		queryKey: [
			"research",
			"experiments",
			experimentId,
			"files",
			filePath,
			{ raw },
		],
		queryFn: async () => {
			const url = `/api/research/experiments/${experimentId}/files/${filePath}${raw ? "?raw=true" : ""}`;
			const res = await fetch(url);
			if (!res.ok) throw new Error(`Failed to fetch file: ${res.statusText}`);
			const contentType = res.headers.get("content-type") || "";
			if (
				contentType.includes("text/html") ||
				contentType.includes("text/plain")
			) {
				return { type: "text" as const, content: await res.text() };
			}
			if (contentType.includes("application/json")) {
				return { type: "json" as const, content: await res.json() };
			}
			if (contentType.includes("image/")) {
				return {
					type: "image" as const,
					content: URL.createObjectURL(await res.blob()),
				};
			}
			return {
				type: "binary" as const,
				content: URL.createObjectURL(await res.blob()),
			};
		},
		enabled: !!experimentId && !!filePath,
		staleTime: 5 * 60 * 1000,
	});
}

export function usePapers() {
	return useQuery({
		queryKey: ["research", "papers"],
		queryFn: () => apiFetch<PaperListResponse>("/research/papers"),
	});
}

export function useStrategySnapshots() {
	return useQuery({
		queryKey: ["research", "strategies"],
		queryFn: () =>
			apiFetch<StrategySnapshotListResponse>("/research/strategies"),
	});
}

// Raw `fetch()` used for format="html" because `apiFetch` always parses JSON;
// the HTML endpoint returns text content.
export function useRunQuantstats(
	runId: string,
	format: "json" | "html" = "json",
) {
	return useQuery({
		queryKey: ["runs", runId, "quantstats", format],
		queryFn: async () => {
			if (format === "html") {
				const res = await fetch(`/api/runs/${runId}/quantstats?format=html`);
				if (!res.ok) throw new Error(res.statusText);
				return await res.text();
			}
			return apiFetch<Record<string, number>>(
				`/runs/${runId}/quantstats?format=json`,
			);
		},
		enabled: !!runId,
		staleTime: 5 * 60 * 1000,
	});
}

export function useRunOOS(runId: string) {
	return useQuery({
		queryKey: ["runs", runId, "oos"],
		queryFn: () => apiFetch<OOSMetadata | null>(`/runs/${runId}/oos`),
		enabled: !!runId,
		staleTime: 5 * 60 * 1000,
	});
}
