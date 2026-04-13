import { Activity, Clock, TrendingUp } from "lucide-react";
import { KpiCard } from "@/components/kpi-card";
import { formatDate, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { RunSummary } from "@/types/api";

interface SummaryBarProps {
  runs: RunSummary[];
  className?: string;
}

export function SummaryBar({ runs, className }: SummaryBarProps) {
  const totalRuns = runs.length;

  const bestRun = runs.reduce<RunSummary | null>((best, r) => {
    if (r.cagr_median == null) return best;
    if (!best || best.cagr_median == null) return r;
    return r.cagr_median > best.cagr_median ? r : best;
  }, null);

  const latestRun = runs.reduce<RunSummary | null>((latest, r) => {
    if (!latest) return r;
    return r.created_at > latest.created_at ? r : latest;
  }, null);

  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-3", className)}>
      <KpiCard label="Total Runs" value={totalRuns} icon={Activity} />
      <KpiCard
        label="Best CAGR"
        value={bestRun?.cagr_median != null ? formatPercent(bestRun.cagr_median) : "—"}
        description={bestRun?.strategy}
        icon={TrendingUp}
      />
      <KpiCard
        label="Latest Run"
        value={latestRun ? formatDate(latestRun.created_at, "short") : "—"}
        description={latestRun?.strategy}
        icon={Clock}
      />
    </div>
  );
}
