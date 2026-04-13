import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { ProgressState } from "@/hooks/use-run-progress";
import { cn } from "@/lib/utils";

export interface ProgressViewProps {
  progress: ProgressState;
  onComplete: (runId: string) => void;
  onError: () => void;
  className?: string;
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function ProgressView({ progress, onComplete, onError, className }: ProgressViewProps) {
  const [startedAt] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (progress.status !== "running") return;
    const timer = setInterval(() => setElapsed(Date.now() - startedAt), 1000);
    return () => clearInterval(timer);
  }, [startedAt, progress.status]);

  useEffect(() => {
    if (progress.status === "completed" && progress.runId) {
      const runId = progress.runId;
      const timer = setTimeout(() => onComplete(runId), 500);
      return () => clearTimeout(timer);
    }
  }, [progress.status, progress.runId, onComplete]);

  const percent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  const rate = elapsed > 0 ? progress.current / (elapsed / 1000) : 0;
  const remaining = rate > 0 ? (progress.total - progress.current) / rate : 0;

  if (progress.status === "failed") {
    return (
      <div className={cn("flex flex-col items-center gap-4 py-12", className)}>
        <XCircle className="size-12 text-destructive" />
        <h2 className="text-xl font-semibold">Backtest Failed</h2>
        <p className="text-sm text-muted-foreground">
          {progress.error ?? "An unexpected error occurred."}
        </p>
        <Button variant="outline" onClick={onError}>
          Try Again
        </Button>
      </div>
    );
  }

  if (progress.status === "completed") {
    return (
      <div className={cn("flex flex-col items-center gap-4 py-12", className)}>
        <CheckCircle2 className="size-12 text-primary" />
        <h2 className="text-xl font-semibold">Backtest Complete!</h2>
        <p className="text-sm text-muted-foreground">Redirecting to results...</p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-6 py-8", className)}>
      <div className="flex items-center gap-3">
        <Loader2 className="size-5 animate-spin text-primary" />
        <h2 className="text-xl font-semibold">Running Backtest...</h2>
      </div>

      <Progress value={percent} className="h-3" />

      <div className="grid grid-cols-3 gap-4 text-center text-sm">
        <div>
          <p className="text-muted-foreground">Iterations</p>
          <p className="font-semibold">
            {progress.current} / {progress.total}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Elapsed</p>
          <p className="font-semibold">{formatElapsed(elapsed)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">ETA</p>
          <p className="font-semibold">
            {progress.current < 3 ? "Calculating..." : formatElapsed(remaining * 1000)}
          </p>
        </div>
      </div>
    </div>
  );
}
