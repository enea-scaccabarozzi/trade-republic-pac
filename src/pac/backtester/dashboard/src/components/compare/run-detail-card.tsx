import { Link } from "@tanstack/react-router";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { AllocationChart } from "@/components/charts/allocation-chart";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import { MetricFormatter } from "@/components/metric-formatter";
import { StatBadge } from "@/components/stat-badge";
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useRunDetail } from "@/hooks/use-run-detail";
import { METRIC_DISPLAY_MAP } from "@/lib/derive";
import type { RunColor } from "@/lib/run-colors";
import { cn } from "@/lib/utils";
import type { RunSummary } from "@/types/api";

export interface RunDetailCardProps {
  runSummary: RunSummary;
  runColor: RunColor;
  className?: string;
}

export function RunDetailCard({ runSummary, runColor, className }: RunDetailCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: detailResponse, isLoading } = useRunDetail(runSummary.run_id, {
    enabled: isExpanded,
  });
  const fullRun = detailResponse?.run;

  return (
    <Card
      className={cn("overflow-hidden", className)}
      style={{ borderLeftColor: runColor.color, borderLeftWidth: 3 }}
    >
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-muted/50"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="inline-block size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: runColor.color }}
              />
              <span className="font-medium truncate">{runSummary.strategy}</span>
              <span className="text-muted-foreground text-xs">
                ({runSummary.run_id.slice(0, 8)})
              </span>
            </div>

            <div className="hidden items-center gap-4 sm:flex">
              <div className="text-right">
                <span className="text-muted-foreground text-xs">CAGR</span>
                <div className="text-sm tabular-nums">
                  <MetricFormatter value={runSummary.cagr_median} format="percent" />
                </div>
              </div>
              <div className="text-right">
                <span className="text-muted-foreground text-xs">Sharpe</span>
                <div className="text-sm tabular-nums">
                  <MetricFormatter value={runSummary.sharpe_median} format="ratio" />
                </div>
              </div>
              <div className="text-right">
                <span className="text-muted-foreground text-xs">Max DD</span>
                <div className="text-sm tabular-nums">
                  <MetricFormatter value={runSummary.max_drawdown_median} format="percent" />
                </div>
              </div>
            </div>

            <ChevronDown
              className={cn(
                "size-4 shrink-0 text-muted-foreground transition-transform duration-200",
                isExpanded && "rotate-180",
              )}
            />
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t px-4 py-4 space-y-4">
            {isLoading && <LoadingSkeleton variant="card" />}

            {fullRun && (
              <>
                <div className="flex flex-wrap gap-2">
                  <StatBadge
                    label="Period"
                    value={`${fullRun.config.start_date.slice(0, 7)} – ${fullRun.config.end_date.slice(0, 7)}`}
                  />
                  <StatBadge label="Iterations" value={fullRun.monte_carlo.iterations} />
                  <StatBadge label="Fee" value={`€${fullRun.config.settlement_fee}`} />
                  <StatBadge label="Spread" value={`${fullRun.config.spread_bps} bps`} />
                </div>

                <AllocationChart
                  allocations={fullRun.allocations}
                  className="[&_[data-slot=chart-container]]:p-0"
                />

                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
                  {Object.entries(METRIC_DISPLAY_MAP).map(([key, info]) => {
                    const metricVal = fullRun.metrics.strategy?.[key]?.median ?? null;
                    return (
                      <div key={key} className="flex items-baseline justify-between gap-2">
                        <span className="text-muted-foreground text-xs">{info.label}</span>
                        <MetricFormatter value={metricVal} format={info.format} />
                      </div>
                    );
                  })}
                </div>

                <Link
                  to="/runs/$id"
                  params={{ id: runSummary.run_id }}
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  View details →
                </Link>
              </>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
