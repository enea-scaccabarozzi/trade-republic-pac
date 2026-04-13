import { useMemo, useState } from "react";
import {
  Area,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartContainer } from "@/components/chart-container";
import { OverlayRenderer } from "@/components/charts/overlay-renderer";
import { OverlayPanel } from "@/components/overlay-panel";
import { computeDrawdownCurve, type DrawdownPoint } from "@/lib/derive";
import { formatChartDate, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  EquityCurvePoint,
  IndicatorSeries,
  StrategyEvent,
  StrategyEventMeta,
} from "@/types/api";

export interface DrawdownChartProps {
  equityCurve: EquityCurvePoint[];
  indicatorSeries: IndicatorSeries[];
  strategyEvents: StrategyEvent[];
  strategyEventMeta: StrategyEventMeta[];
  className?: string;
}

function DrawdownTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: DrawdownPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="text-muted-foreground mb-1 text-xs">{d.date}</p>
      <p>
        Drawdown: <span className="font-medium text-danger">{formatPercent(d.drawdown)}</span>
      </p>
    </div>
  );
}

export function DrawdownChart({
  equityCurve,
  indicatorSeries,
  strategyEvents,
  strategyEventMeta,
  className,
}: DrawdownChartProps) {
  const [layersOpen, setLayersOpen] = useState(false);

  const drawdownData = useMemo(() => computeDrawdownCurve(equityCurve), [equityCurve]);
  const dateRange = useMemo(() => drawdownData.map((p) => p.date), [drawdownData]);

  return (
    <ChartContainer
      title="Drawdown from Peak"
      description="Maximum decline from historical peak"
      onLayersToggle={() => setLayersOpen((v) => !v)}
      layersOpen={layersOpen}
      layersContent={
        <OverlayPanel
          chartType="drawdown"
          indicatorSeries={indicatorSeries}
          strategyEventMeta={strategyEventMeta}
        />
      }
      className={cn(className)}
    >
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={drawdownData}>
          <XAxis
            dataKey="date"
            tickFormatter={formatChartDate}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "var(--color-border)" }}
          />
          <YAxis
            yAxisId="main"
            tickFormatter={(v: number) => formatPercent(v, 0)}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            domain={["dataMin", 0]}
            width={50}
          />
          <Tooltip content={<DrawdownTooltip />} />

          <ReferenceLine yAxisId="main" y={0} stroke="var(--color-border)" strokeWidth={1} />

          <Area
            yAxisId="main"
            type="monotone"
            dataKey="drawdown"
            fill="var(--color-danger)"
            fillOpacity={0.15}
            stroke="var(--color-danger)"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />

          <OverlayRenderer
            chartType="drawdown"
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
