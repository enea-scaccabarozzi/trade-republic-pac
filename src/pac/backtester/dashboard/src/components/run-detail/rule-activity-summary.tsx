import { useMemo } from "react";
import { KpiCard } from "@/components/kpi-card";
import { StatBadge } from "@/components/stat-badge";
import { computeRuleStats } from "@/lib/derive";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SignalRecord } from "@/types/api";

interface RuleActivitySummaryProps {
  signalLog: SignalRecord[];
  startDate: string;
  endDate: string;
  className?: string;
}

function formatRuleName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const SEVERITY_VARIANT: Record<string, "success" | "warning" | "danger" | "info" | "neutral"> = {
  critical: "danger",
  warning: "warning",
  info: "info",
};

export function RuleActivitySummary({
  signalLog,
  startDate,
  endDate,
  className,
}: RuleActivitySummaryProps) {
  const ruleStats = useMemo(
    () => computeRuleStats(signalLog, startDate, endDate),
    [signalLog, startDate, endDate],
  );

  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {ruleStats.map((stat) => (
        <KpiCard
          key={stat.ruleName}
          label={formatRuleName(stat.ruleName)}
          value={`${stat.triggerCount} trigger${stat.triggerCount !== 1 ? "s" : ""}`}
          description={
            stat.avgFrequencyDays !== null
              ? `Every ~${Math.round(stat.avgFrequencyDays)} days`
              : "Single occurrence"
          }
        >
          <div className="mt-2 flex flex-wrap gap-1">
            {Object.entries(stat.severityBreakdown).map(([severity, count]) => (
              <StatBadge
                key={severity}
                label={`${count}`}
                value={severity}
                variant={SEVERITY_VARIANT[severity] ?? "neutral"}
              />
            ))}
          </div>
          <p className="text-muted-foreground mt-1 text-xs">
            {formatDate(stat.firstTrigger, "short")} – {formatDate(stat.lastTrigger, "short")}
          </p>
        </KpiCard>
      ))}
    </div>
  );
}
