import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useOverlayStore } from "@/stores/overlay-store";
import type { IndicatorSeries, StrategyEventMeta } from "@/types/api";

export type ChartType = "equity" | "allocation" | "drawdown";

export interface OverlayPanelProps {
  chartType: ChartType;
  indicatorSeries: IndicatorSeries[];
  strategyEventMeta: StrategyEventMeta[];
  className?: string;
}

function isCompatible(series: IndicatorSeries, chartType: ChartType): boolean {
  switch (chartType) {
    case "equity":
      return series.meta.kind !== "event";
    case "drawdown":
      return series.meta.kind === "continuous" || series.meta.kind === "boolean";
    case "allocation":
      return false;
  }
}

function groupByGroup(items: IndicatorSeries[]): Record<string, IndicatorSeries[]> {
  const groups: Record<string, IndicatorSeries[]> = {};
  for (const item of items) {
    const group = item.meta.group || "Other";
    const existing = groups[group];
    if (existing) {
      existing.push(item);
    } else {
      groups[group] = [item];
    }
  }
  return groups;
}

export function OverlayPanel({
  chartType,
  indicatorSeries,
  strategyEventMeta,
  className,
}: OverlayPanelProps) {
  const { visibleOverlays, toggleOverlay } = useOverlayStore();

  const compatible = indicatorSeries.filter((s) => isCompatible(s, chartType));
  const grouped = groupByGroup(compatible);

  const showEvents =
    (chartType === "equity" || chartType === "drawdown") && strategyEventMeta.length > 0;

  const hasContent = compatible.length > 0 || showEvents;

  if (!hasContent) {
    return <p className={cn("text-muted-foreground text-xs", className)}>No overlays available</p>;
  }

  return (
    <div className={cn("space-y-3", className)}>
      {Object.entries(grouped).map(([group, series]) => (
        <div key={group}>
          <p className="text-muted-foreground mb-1.5 text-xs font-medium uppercase tracking-wider">
            {group}
          </p>
          <div className="space-y-1.5">
            {series.map((s) => {
              const key = `${chartType}:${s.meta.key}`;
              return (
                <div key={key} className="flex cursor-pointer items-center justify-between gap-2">
                  <span className="text-sm">{s.meta.display_name}</span>
                  <Switch
                    checked={!!visibleOverlays[key]}
                    onCheckedChange={() => toggleOverlay(key)}
                    className="scale-75"
                  />
                </div>
              );
            })}
          </div>
        </div>
      ))}
      {showEvents && (
        <div>
          <p className="text-muted-foreground mb-1.5 text-xs font-medium uppercase tracking-wider">
            Events
          </p>
          <div className="space-y-1.5">
            {strategyEventMeta.map((meta) => {
              const key = `${chartType}:event:${meta.key}`;
              return (
                <div key={key} className="flex cursor-pointer items-center justify-between gap-2">
                  <span className="text-sm">{meta.display_name}</span>
                  <Switch
                    checked={!!visibleOverlays[key]}
                    onCheckedChange={() => toggleOverlay(key)}
                    className="scale-75"
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
