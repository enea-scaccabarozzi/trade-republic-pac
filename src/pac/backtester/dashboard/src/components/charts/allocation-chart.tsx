import { useMemo } from "react";
import { Area, AreaChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartContainer } from "@/components/chart-container";
import { flattenAllocations } from "@/lib/derive";
import { formatChartDate, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AllocationPoint } from "@/types/api";

export interface AllocationChartProps {
  allocations: AllocationPoint[];
  className?: string;
}

const CHART_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
  "var(--color-chart-7)",
  "var(--color-chart-8)",
];

function AllocationTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="text-muted-foreground mb-1 text-xs">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-1.5">
          <span className="inline-block size-2 rounded-full" style={{ background: p.color }} />
          {p.name}: <span className="font-medium">{formatPercent(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function AllocationChart({ allocations, className }: AllocationChartProps) {
  const { data, assetIds } = useMemo(() => flattenAllocations(allocations), [allocations]);

  if (data.length === 0) {
    return (
      <ChartContainer title="Asset Allocation" description="Portfolio composition over time">
        <p className="text-muted-foreground py-12 text-center text-sm">No allocation data</p>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer
      title="Asset Allocation"
      description="Portfolio composition over time"
      className={cn(className)}
    >
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          <XAxis
            dataKey="date"
            tickFormatter={formatChartDate}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "var(--color-border)" }}
          />
          <YAxis
            tickFormatter={(v: number) => formatPercent(v, 0)}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            domain={[0, 1]}
            width={50}
          />
          <Tooltip content={<AllocationTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {assetIds.map((id, i) => {
            const isCash = id.toLowerCase() === "cash";
            const color = isCash
              ? "var(--color-muted-foreground)"
              : (CHART_COLORS[i % CHART_COLORS.length] ?? "var(--color-chart-1)");
            return (
              <Area
                key={id}
                type="monotone"
                dataKey={id}
                stackId="1"
                fill={color}
                fillOpacity={0.7}
                stroke={color}
                strokeWidth={0}
                isAnimationActive={false}
              />
            );
          })}
        </AreaChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
