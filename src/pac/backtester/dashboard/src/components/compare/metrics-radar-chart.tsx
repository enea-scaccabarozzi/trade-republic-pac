import { useMemo } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import { ChartContainer } from "@/components/chart-container";
import { computeRadarData, METRIC_DISPLAY_MAP } from "@/lib/derive";
import { formatPercent, formatRatio } from "@/lib/format";
import type { RunColor } from "@/lib/run-colors";
import { cn } from "@/lib/utils";
import type { RunResult } from "@/types/api";

export interface MetricsRadarChartProps {
  runs: RunResult[];
  runColors: RunColor[];
  className?: string;
}

const RADAR_METRICS = ["cagr", "sharpe", "sortino", "calmar", "max_drawdown", "volatility"];

function formatRawValue(key: string, value: number): string {
  const info = METRIC_DISPLAY_MAP[key];
  if (!info) return String(value);
  if (info.format === "percent") return formatPercent(value);
  return formatRatio(value);
}

function RadarTooltipContent({
  active,
  payload,
  runColors,
}: {
  active?: boolean;
  // biome-ignore lint/suspicious/noExplicitAny: recharts tooltip payload type
  payload?: Array<{ payload: any }>;
  runColors: RunColor[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="mb-1 font-medium">{d.metric}</p>
      {runColors.map((rc) => {
        const score = d[rc.runId] as number;
        const raw = d[`_raw_${rc.runId}`] as number;
        return (
          <div key={rc.runId} className="flex items-center gap-1.5 text-xs">
            <span
              className="inline-block size-2 rounded-full"
              style={{ backgroundColor: rc.color }}
            />
            <span className="text-muted-foreground">{rc.label}:</span>
            <span className="font-medium">{score}/100</span>
            <span className="text-muted-foreground">
              ({raw != null ? formatRawValue(d.metricKey, raw) : "N/A"})
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function MetricsRadarChart({ runs, runColors, className }: MetricsRadarChartProps) {
  const radarData = useMemo(
    () =>
      computeRadarData(
        runs.map((r) => ({ runId: r.run_id, metrics: r.metrics })),
        RADAR_METRICS,
        METRIC_DISPLAY_MAP,
      ),
    [runs],
  );

  return (
    <ChartContainer
      title="Metrics Comparison"
      description="Normalized 0–100 scale — higher is better for all axes"
      className={cn(className)}
    >
      {runs.length === 1 && (
        <p className="text-muted-foreground mb-2 text-center text-xs italic">
          Add more runs for comparison.
        </p>
      )}
      <ResponsiveContainer width="100%" height={400}>
        <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="80%">
          <PolarGrid gridType="polygon" />
          <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          {runColors.map((rc) => (
            <Radar
              key={rc.runId}
              dataKey={rc.runId}
              stroke={rc.color}
              fill={rc.color}
              fillOpacity={0.1}
              strokeWidth={2}
              dot={{ r: 3, fill: rc.color }}
            />
          ))}
          <RechartsTooltip content={<RadarTooltipContent runColors={runColors} />} />
        </RadarChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
