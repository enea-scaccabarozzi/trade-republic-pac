import { useMemo } from "react";
import { Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartContainer } from "@/components/chart-container";
import { computeTradeFrequency } from "@/lib/derive";
import type { TradeRecord } from "@/types/api";

interface TradeFrequencyChartProps {
  trades: TradeRecord[];
  className?: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((sum, p) => sum + p.value, 0);
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-popover-foreground shadow-md">
      <p className="text-sm font-medium">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-xs" style={{ color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
      <p className="text-muted-foreground mt-1 text-xs">Total: {total}</p>
    </div>
  );
}

export function TradeFrequencyChart({ trades, className }: TradeFrequencyChartProps) {
  const frequencyData = useMemo(() => computeTradeFrequency(trades), [trades]);

  if (frequencyData.length === 0) return null;

  return (
    <ChartContainer title="Trade Frequency" description="Trades per month" className={className}>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={frequencyData}>
          <XAxis
            dataKey="monthLabel"
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "var(--color-muted-foreground)", fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="buy" stackId="trades" fill="var(--color-success)" name="Buy" />
          <Bar dataKey="sell" stackId="trades" fill="var(--color-danger)" name="Sell" />
          <Bar dataKey="skipped" stackId="trades" fill="var(--color-warning)" name="Skipped" />
          <Legend />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
