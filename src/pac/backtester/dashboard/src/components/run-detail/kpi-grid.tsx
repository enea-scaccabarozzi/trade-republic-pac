import { BarChart3, DollarSign, Percent, Receipt, TrendingDown, TrendingUp } from "lucide-react";
import { ConfidenceValue } from "@/components/confidence-value";
import { KpiCard } from "@/components/kpi-card";
import { formatCurrency, formatInteger, formatPercent, formatRatio } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { MetricValue, SummaryStats } from "@/types/api";

export interface KpiGridProps {
  summary: SummaryStats;
  metrics: Record<string, Record<string, MetricValue>>;
  className?: string;
}

function getMetricMedian(
  metrics: Record<string, Record<string, MetricValue>>,
  group: string,
  key: string,
): number | null {
  return metrics[group]?.[key]?.median ?? null;
}

export function KpiGrid({ summary, metrics, className }: KpiGridProps) {
  const finalValueMedian = summary.final_value.median;
  const totalInvested = summary.total_invested;
  const totalReturn = totalInvested > 0 ? (finalValueMedian - totalInvested) / totalInvested : null;

  const cagr = getMetricMedian(metrics, "strategy", "cagr");
  const sharpe = getMetricMedian(metrics, "strategy", "sharpe");
  const maxDrawdown = getMetricMedian(metrics, "strategy", "max_drawdown");

  return (
    <div className={cn("grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6", className)}>
      <KpiCard label="Final Value" value={formatCurrency(finalValueMedian)} icon={DollarSign}>
        <div className="mt-2">
          <ConfidenceValue
            ci={summary.final_value}
            format="currency"
            showRange
            decimals={0}
            className="text-xs"
          />
        </div>
      </KpiCard>

      <KpiCard
        label="Total Return"
        value={totalReturn != null ? formatPercent(totalReturn) : "—"}
        icon={Percent}
      />

      <KpiCard label="CAGR" value={cagr != null ? formatPercent(cagr) : "—"} icon={TrendingUp} />

      <KpiCard
        label="Sharpe Ratio"
        value={sharpe != null ? formatRatio(sharpe) : "—"}
        icon={BarChart3}
      />

      <KpiCard
        label="Max Drawdown"
        value={maxDrawdown != null ? formatPercent(maxDrawdown) : "—"}
        icon={TrendingDown}
      />

      <KpiCard
        label="Fees & Trades"
        value={formatCurrency(summary.total_fees.median, "EUR", 0)}
        description={`${formatInteger(summary.total_trades.median)} trades`}
        icon={Receipt}
      />
    </div>
  );
}
