import { Check } from "lucide-react";
import { useMemo } from "react";
import { MetricFormatter } from "@/components/metric-formatter";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { METRIC_DISPLAY_MAP } from "@/lib/derive";
import { formatPercent, formatRatio } from "@/lib/format";
import type { RunColor } from "@/lib/run-colors";
import { cn } from "@/lib/utils";
import type { RunResult } from "@/types/api";

export interface CompareMetricsTableProps {
  runs: RunResult[];
  runColors: RunColor[];
  className?: string;
}

const METRIC_KEYS = ["cagr", "sharpe", "sortino", "calmar", "max_drawdown", "volatility"];

function findBest(values: (number | null)[], invertColor: boolean): number {
  const valid = values
    .map((v, i) => ({ v, i }))
    .filter((x): x is { v: number; i: number } => x.v != null);
  if (valid.length === 0) return -1;

  if (invertColor) {
    return valid.reduce((best, curr) => (Math.abs(curr.v) < Math.abs(best.v) ? curr : best)).i;
  }
  return valid.reduce((best, curr) => (curr.v > best.v ? curr : best)).i;
}

function formatDelta(key: string, delta: number): string {
  const info = METRIC_DISPLAY_MAP[key];
  if (!info) return "";
  if (info.format === "percent") return formatPercent(delta);
  return formatRatio(delta);
}

export function CompareMetricsTable({ runs, runColors, className }: CompareMetricsTableProps) {
  const winCounts = useMemo(() => {
    const counts = new Map<number, number>();
    for (const key of METRIC_KEYS) {
      const info = METRIC_DISPLAY_MAP[key];
      if (!info) continue;
      const values = runs.map((r) => r.metrics.strategy?.[key]?.median ?? null);
      const bestIdx = findBest(values, info.invertColor);
      if (bestIdx >= 0) {
        counts.set(bestIdx, (counts.get(bestIdx) ?? 0) + 1);
      }
    }
    return counts;
  }, [runs]);

  return (
    <div className={cn("overflow-x-auto rounded-lg border bg-card", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky left-0 bg-card">Metric</TableHead>
            {runColors.map((rc) => (
              <TableHead key={rc.runId}>
                <div className="flex items-center gap-1.5">
                  <span
                    className="inline-block size-2.5 rounded-full"
                    style={{ backgroundColor: rc.color }}
                  />
                  <span className="whitespace-nowrap">{rc.label}</span>
                </div>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {METRIC_KEYS.map((key) => {
            const info = METRIC_DISPLAY_MAP[key];
            if (!info) return null;
            const values = runs.map((r) => r.metrics.strategy?.[key]?.median ?? null);
            const bestIdx = findBest(values, info.invertColor);

            return (
              <TableRow key={key} className="even:bg-muted/50">
                <TableCell className="sticky left-0 bg-card font-medium">{info.label}</TableCell>
                {values.map((val, i) => {
                  const isBest = i === bestIdx;
                  const bestVal = bestIdx >= 0 ? values[bestIdx] : null;
                  const delta = val != null && bestVal != null && !isBest ? val - bestVal : null;

                  return (
                    <TableCell key={runColors[i]?.runId ?? i}>
                      <div className="space-y-0.5">
                        <div className={cn(isBest && "font-bold text-success")}>
                          <MetricFormatter
                            value={val}
                            format={info.format === "percent" ? "percent" : "ratio"}
                          />
                        </div>
                        {isBest && (
                          <div className="text-success flex items-center gap-0.5 text-[11px]">
                            <Check className="size-3" />
                            Best
                          </div>
                        )}
                        {delta != null && (
                          <div className="text-muted-foreground text-[11px]">
                            ({formatDelta(key, delta)} from best)
                          </div>
                        )}
                      </div>
                    </TableCell>
                  );
                })}
              </TableRow>
            );
          })}
          <TableRow className="border-t-2">
            <TableCell className="sticky left-0 bg-card font-medium">Win Count</TableCell>
            {runColors.map((_, i) => (
              <TableCell key={runColors[i]?.runId ?? i} className="font-semibold tabular-nums">
                {winCounts.get(i) ?? 0} / {METRIC_KEYS.length}
              </TableCell>
            ))}
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
