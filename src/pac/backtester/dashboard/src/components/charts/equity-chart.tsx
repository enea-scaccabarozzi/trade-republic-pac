import { useMemo, useState } from "react";
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartContainer } from "@/components/chart-container";
import { OverlayRenderer } from "@/components/charts/overlay-renderer";
import { OverlayPanel } from "@/components/overlay-panel";
import { Switch } from "@/components/ui/switch";
import { formatChartDate, formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  EquityCurvePoint,
  IndicatorSeries,
  StrategyEvent,
  StrategyEventMeta,
} from "@/types/api";

export interface EquityChartProps {
  equityCurve: EquityCurvePoint[];
  benchmarkEquityCurve: EquityCurvePoint[] | null;
  indicatorSeries: IndicatorSeries[];
  strategyEvents: StrategyEvent[];
  strategyEventMeta: StrategyEventMeta[];
  className?: string;
}

interface ChartDataPoint {
  date: string;
  p5: number;
  median: number;
  p95: number;
  bandWidth: number;
  benchmark_median: number | null;
}

function EquityTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartDataPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="text-muted-foreground mb-1 text-xs">{d.date}</p>
      <p>
        Median: <span className="font-medium">{formatCurrency(d.median)}</span>
      </p>
      <p className="text-muted-foreground text-xs">
        P5: {formatCurrency(d.p5)} — P95: {formatCurrency(d.p95)}
      </p>
      {d.benchmark_median != null && (
        <p className="text-muted-foreground text-xs">
          Benchmark: {formatCurrency(d.benchmark_median)}
        </p>
      )}
    </div>
  );
}

export function EquityChart({
  equityCurve,
  benchmarkEquityCurve,
  indicatorSeries,
  strategyEvents,
  strategyEventMeta,
  className,
}: EquityChartProps) {
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [layersOpen, setLayersOpen] = useState(false);

  const hasBenchmark = benchmarkEquityCurve != null && benchmarkEquityCurve.length > 0;

  const chartData = useMemo(() => {
    const benchmarkMap = new Map((benchmarkEquityCurve ?? []).map((p) => [p.date, p]));
    return equityCurve.map((p) => ({
      ...p,
      bandWidth: p.p95 - p.p5,
      benchmark_median: benchmarkMap.get(p.date)?.median ?? null,
    }));
  }, [equityCurve, benchmarkEquityCurve]);

  const dateRange = useMemo(() => equityCurve.map((p) => p.date), [equityCurve]);

  const headerExtra = hasBenchmark ? (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="text-muted-foreground">Benchmark</span>
      <Switch checked={showBenchmark} onCheckedChange={setShowBenchmark} className="scale-75" />
    </div>
  ) : undefined;

  return (
    <ChartContainer
      title="Equity Curve"
      description="Portfolio value with P5/P95 confidence bands"
      onLayersToggle={() => setLayersOpen((v) => !v)}
      layersOpen={layersOpen}
      layersContent={
        <OverlayPanel
          chartType="equity"
          indicatorSeries={indicatorSeries}
          strategyEventMeta={strategyEventMeta}
        />
      }
      className={cn(className)}
    >
      {headerExtra && <div className="mb-3 flex justify-end">{headerExtra}</div>}
      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={chartData}>
          <XAxis
            dataKey="date"
            tickFormatter={formatChartDate}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "var(--color-border)" }}
          />
          <YAxis
            yAxisId="main"
            tickFormatter={(v: number) => formatCurrency(v, "EUR", 0)}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={70}
          />
          <Tooltip content={<EquityTooltip />} />

          {/* P5/P95 confidence band via stacked areas */}
          <Area
            yAxisId="main"
            type="monotone"
            dataKey="p5"
            stackId="band"
            fill="transparent"
            stroke="none"
            isAnimationActive={false}
          />
          <Area
            yAxisId="main"
            type="monotone"
            dataKey="bandWidth"
            stackId="band"
            fill="var(--color-chart-1)"
            fillOpacity={0.1}
            stroke="none"
            isAnimationActive={false}
          />

          {/* Median line */}
          <Line
            yAxisId="main"
            type="monotone"
            dataKey="median"
            stroke="var(--color-chart-1)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />

          {/* Benchmark line */}
          {hasBenchmark && showBenchmark && (
            <Line
              yAxisId="main"
              type="monotone"
              dataKey="benchmark_median"
              stroke="var(--color-muted-foreground)"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          )}

          <OverlayRenderer
            chartType="equity"
            indicatorSeries={indicatorSeries}
            strategyEvents={strategyEvents}
            strategyEventMeta={strategyEventMeta}
            dateRange={dateRange}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
