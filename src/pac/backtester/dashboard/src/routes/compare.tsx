import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { BarChart3, X } from "lucide-react";
import { useCallback, useEffect, useMemo } from "react";
import { z } from "zod";
import { CompareEquityChart } from "@/components/compare/compare-equity-chart";
import { CompareMetricsTable } from "@/components/compare/compare-metrics-table";
import { MetricsRadarChart } from "@/components/compare/metrics-radar-chart";
import { RunColorLegend } from "@/components/compare/run-color-legend";
import { RunDetailCard } from "@/components/compare/run-detail-card";
import { RunSelectorCombobox } from "@/components/compare/run-selector-combobox";
import { SignalActivityHeatmap } from "@/components/compare/signal-activity-heatmap";
import { EmptyState } from "@/components/empty-state";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { useCompareRuns } from "@/hooks/use-compare-runs";
import { useRuns } from "@/hooks/use-runs";
import { assignRunColors } from "@/lib/run-colors";

const compareSearchSchema = z.object({
  ids: z.string().optional(),
});

export const Route = createFileRoute("/compare")({
  validateSearch: compareSearchSchema,
  component: CompareView,
});

function CompareView() {
  const navigate = useNavigate();
  const { ids: idsParam } = Route.useSearch();

  const selectedRunIds = useMemo(
    () => (idsParam ? idsParam.split(",").filter(Boolean) : []),
    [idsParam],
  );

  const setSelection = useCallback(
    (ids: string[]) => {
      navigate({
        to: "/compare",
        search: { ids: ids.length > 0 ? ids.join(",") : undefined },
        replace: true,
      });
    },
    [navigate],
  );

  const clearSelection = useCallback(() => setSelection([]), [setSelection]);

  // Escape key clears selection (only when no popover is open)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || selectedRunIds.length === 0) return;
      const activePopover = document.querySelector(
        "[data-state='open'][data-radix-popper-content-wrapper]",
      );
      if (activePopover) return;
      clearSelection();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [selectedRunIds, clearSelection]);

  const { data: runsList } = useRuns();
  const { runs, isLoading, errors } = useCompareRuns(selectedRunIds);

  const runColors = useMemo(() => assignRunColors(runs), [runs]);

  const errorCount = Object.keys(errors).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compare Runs"
        description="Multi-run analysis"
        actions={
          selectedRunIds.length > 0 ? (
            <Button variant="outline" size="sm" className="gap-1.5" onClick={clearSelection}>
              <X className="size-3.5" />
              Clear All
            </Button>
          ) : undefined
        }
      />

      <RunSelectorCombobox
        runs={runsList?.runs ?? []}
        selectedIds={selectedRunIds}
        onSelectionChange={setSelection}
        maxSelections={6}
      />

      {selectedRunIds.length === 0 && (
        <EmptyState
          icon={BarChart3}
          title="No runs selected"
          description="Search and select 2–6 backtest runs above to compare them."
        />
      )}

      {isLoading && <LoadingSkeleton variant="page" />}

      {errorCount > 0 && (
        <div className="text-sm text-destructive">
          Failed to load {errorCount} run(s). Showing available data.
        </div>
      )}

      {runs.length >= 2 && (
        <div className="space-y-6">
          <RunColorLegend runColors={runColors} />

          <CompareEquityChart runs={runs} runColors={runColors} />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <MetricsRadarChart runs={runs} runColors={runColors} />
            <CompareMetricsTable runs={runs} runColors={runColors} />
          </div>

          <SignalActivityHeatmap runs={runs} runColors={runColors} />

          <div className="space-y-3">
            <h3 className="text-sm font-medium">Run Details</h3>
            {runColors.map((rc) => {
              const summary = (runsList?.runs ?? []).find((r) => r.run_id === rc.runId);
              if (!summary) return null;
              return <RunDetailCard key={rc.runId} runSummary={summary} runColor={rc} />;
            })}
          </div>
        </div>
      )}

      {runs.length === 1 && !isLoading && (
        <div className="text-muted-foreground mt-6 text-center text-sm">
          Select at least one more run to start comparing.
        </div>
      )}
    </div>
  );
}
