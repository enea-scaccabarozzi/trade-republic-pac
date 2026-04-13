import { useCallback, useEffect, useState } from "react";

export interface ProgressState {
  current: number;
  total: number;
  status: "running" | "completed" | "failed";
  runId: string | null;
  error: string | null;
}

export function useRunProgress(jobId: string | null) {
  const [progress, setProgress] = useState<ProgressState | null>(null);

  useEffect(() => {
    if (!jobId) return;
    const es = new EventSource(`/api/runs/${jobId}/progress`);

    es.onmessage = (event) => {
      const data = JSON.parse(event.data as string);
      setProgress({
        current: data.current,
        total: data.total,
        status: data.status,
        runId: data.run_id ?? data.runId ?? null,
        error: data.error ?? null,
      });
      if (data.status === "completed" || data.status === "failed") {
        es.close();
      }
    };

    es.onerror = () => {
      es.close();
      setProgress((prev) =>
        prev && prev.status === "running"
          ? { ...prev, status: "failed", error: "Connection lost" }
          : prev,
      );
    };

    return () => es.close();
  }, [jobId]);

  const reset = useCallback(() => setProgress(null), []);
  return { progress, reset };
}
