import { MetricFormatter } from "@/components/metric-formatter";
import { cn } from "@/lib/utils";

interface ConfidenceValueProps {
  ci: { p5: number; median: number; p95: number };
  format: "percent" | "currency" | "ratio" | "decimal";
  showRange?: boolean;
  decimals?: number;
  className?: string;
}

export function ConfidenceValue({
  ci,
  format,
  showRange = false,
  decimals,
  className,
}: ConfidenceValueProps) {
  return (
    <div className={cn("flex flex-col", className)}>
      <MetricFormatter value={ci.median} format={format} decimals={decimals} />
      {showRange && (
        <span className="text-muted-foreground text-xs">
          <MetricFormatter value={ci.p5} format={format} decimals={decimals} />
          {" – "}
          <MetricFormatter value={ci.p95} format={format} decimals={decimals} />
        </span>
      )}
    </div>
  );
}
