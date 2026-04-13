import { ConfigSummary } from "@/components/run-detail/config-summary";
import { KpiGrid } from "@/components/run-detail/kpi-grid";
import { MetricsTable } from "@/components/run-detail/metrics-table";
import type { RunResult } from "@/types/api";

export interface OverviewTabProps {
  run: RunResult;
}

export function OverviewTab({ run }: OverviewTabProps) {
  return (
    <div className="flex flex-col gap-6">
      <ConfigSummary config={run.config} monteCarlo={run.monte_carlo} />
      <KpiGrid summary={run.summary} metrics={run.metrics} />
      <MetricsTable metrics={run.metrics} />
    </div>
  );
}
