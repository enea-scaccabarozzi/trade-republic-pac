import type { RunColor } from "@/lib/run-colors";
import { cn } from "@/lib/utils";

export interface RunColorLegendProps {
  runColors: RunColor[];
  className?: string;
}

export function RunColorLegend({ runColors, className }: RunColorLegendProps) {
  return (
    <div className={cn("flex flex-wrap gap-x-4 gap-y-2", className)}>
      {runColors.map((rc) => (
        <div key={rc.runId} className="flex items-center gap-1.5 text-sm">
          <span
            className="inline-block size-3 rounded-full"
            style={{ backgroundColor: rc.color }}
          />
          <span className="text-muted-foreground">{rc.label}</span>
        </div>
      ))}
    </div>
  );
}
