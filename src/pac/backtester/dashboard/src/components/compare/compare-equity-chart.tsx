import { useMemo, useState } from "react";
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartContainer } from "@/components/chart-container";
import { BrushZoomBar } from "@/components/charts/brush-zoom-bar";
import { OverlayRenderer } from "@/components/charts/overlay-renderer";
import { OverlayPanel } from "@/components/overlay-panel";
import { Switch } from "@/components/ui/switch";
import { useBrushZoom } from "@/hooks/use-brush-zoom";
import { normalizeEquityCurves } from "@/lib/derive";
import { formatChartDate, formatCurrency } from "@/lib/format";
import type { RunColor } from "@/lib/run-colors";
import { cn } from "@/lib/utils";
import type { RunResult } from "@/types/api";

export interface CompareEquityChartProps {
  runs: RunResult[];
  runColors: RunColor[];
  className?: string;
}

interface CompareTooltipProps {
  active?: boolean;
  // biome-ignore lint/suspicious/noExplicitAny: recharts tooltip payload type
  payload?: Array<{ payload: any }>;
  runColors: RunColor[];
}

function CompareEquityTooltip({ active, payload, runColors }: CompareTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="text-muted-foreground mb-1 text-xs">{d.date}</p>
      {runColors.map((rc) => {
        const val = d[rc.runId] as number | null;
        if (val == null) return null;
        return (
          <div key={rc.runId} className="flex items-center gap-1.5">
            <span
              className="inline-block size-2 rounded-full"
              style={{ backgroundColor: rc.color }}
            />
            <span className="text-muted-foreground text-xs">{rc.label}:</span>
            <span className="font-medium">{formatCurrency(val)}</span>
          </div>
        );
      })}
    </div>
  );
}

export function CompareEquityChart({ runs, runColors, className }: CompareEquityChartProps) {
  const [showBands, setShowBands] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const bandsDisabled = runs.length > 3;

  const normalizedData = useMemo(
    () =>
      normalizeEquityCurves(runs.map((r) => ({ runId: r.run_id, equityCurve: r.equity_curve }))),
    [runs],
  );

  const chartData = useMemo(() => {
    return normalizedData.map((point) => {
      const enriched = { ...point };
      for (const rc of runColors) {
        const p5 = point[`${rc.runId}_p5`] as number | null;
        const p95 = point[`${rc.runId}_p95`] as number | null;
        enriched[`${rc.runId}_bandWidth`] = p5 != null && p95 != null ? p95 - p5 : null;
      }
      return enriched;
    });
  }, [normalizedData, runColors]);

  const { zoom, handleBrushChange, resetZoom, isZoomed } = useBrushZoom(chartData.length);
  const visibleData = useMemo(
    () => chartData.slice(zoom.startIndex, zoom.endIndex + 1),
    [chartData, zoom.startIndex, zoom.endIndex],
  );

  const dateRange = useMemo(() => visibleData.map((p) => p.date), [visibleData]);

  const allIndicatorSeries = useMemo(() => {
    const seen = new Set<string>();
    return runs.flatMap((r) =>
      r.indicator_series.filter((s) => {
        const key = `${r.run_id}:${s.meta.key}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }),
    );
  }, [runs]);

  const allStrategyEvents = useMemo(() => runs.flatMap((r) => r.strategy_events), [runs]);
  const allStrategyEventMeta = useMemo(() => {
    const seen = new Set<string>();
    return runs.flatMap((r) =>
      r.strategy_event_meta.filter((m) => {
        if (seen.has(m.key)) return false;
        seen.add(m.key);
        return true;
      }),
    );
  }, [runs]);

  const effectiveShowBands = showBands && !bandsDisabled;

  const brushEquityCurve = useMemo(() => {
    const first = runs[0];
    return first ? first.equity_curve : [];
  }, [runs]);

  return (
    <ChartContainer
      title="Equity Curves"
      description="Portfolio value overlay across selected runs"
      onLayersToggle={() => setLayersOpen((v) => !v)}
      layersOpen={layersOpen}
      layersContent={
        <OverlayPanel
          chartType="equity"
          indicatorSeries={allIndicatorSeries}
          strategyEventMeta={allStrategyEventMeta}
        />
      }
      className={cn(className)}
    >
      <div className="mb-3 flex items-center justify-end gap-1.5 text-xs">
        <span className={cn("text-muted-foreground", bandsDisabled && "opacity-50")}>CI Bands</span>
        <Switch
          checked={effectiveShowBands}
          onCheckedChange={setShowBands}
          disabled={bandsDisabled}
          className="scale-75"
        />
        {bandsDisabled && (
          <span className="text-muted-foreground text-[11px] italic">
            (disabled — too many runs)
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={visibleData}>
          <XAxis
            dataKey="date"
            tickFormatter={formatChartDate}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "var(--color-border)" }}
          />
          <YAxis
            tickFormatter={(v: number) => formatCurrency(v, "EUR", 0)}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={70}
          />
          <Tooltip content={<CompareEquityTooltip runColors={runColors} />} />

          {runColors.map((rc) => (
            <Line
              key={rc.runId}
              type="monotone"
              dataKey={rc.runId}
              stroke={rc.color}
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          ))}

          {effectiveShowBands &&
            runColors.map((rc) => (
              <Area
                key={`band-${rc.runId}`}
                type="monotone"
                dataKey={`${rc.runId}_bandWidth`}
                stackId={`band-${rc.runId}`}
                fill={rc.color}
                fillOpacity={0.08}
                stroke="none"
                isAnimationActive={false}
                baseLine={0}
              />
            ))}

          <OverlayRenderer
            chartType="equity"
            indicatorSeries={allIndicatorSeries}
            strategyEvents={allStrategyEvents}
            strategyEventMeta={allStrategyEventMeta}
            dateRange={dateRange}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <BrushZoomBar
        equityCurve={brushEquityCurve}
        zoom={zoom}
        onBrushChange={handleBrushChange}
        onReset={resetZoom}
        isZoomed={isZoomed}
        className="mt-2"
      />
    </ChartContainer>
  );
}
