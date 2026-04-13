import {
  formatCurrency,
  formatDecimal,
  formatInteger,
  formatPercent,
  formatRatio,
} from "@/lib/format";
import { cn } from "@/lib/utils";

interface MetricFormatterProps {
  value: number | null | undefined;
  format: "percent" | "currency" | "ratio" | "integer" | "decimal";
  decimals?: number;
  currency?: string;
  colorize?: boolean;
  fallback?: string;
  className?: string;
}

function formatValue(
  value: number,
  format: MetricFormatterProps["format"],
  decimals?: number,
  currency?: string,
): string {
  switch (format) {
    case "percent":
      return formatPercent(value, decimals);
    case "currency":
      return formatCurrency(value, currency, decimals);
    case "ratio":
      return formatRatio(value, decimals);
    case "integer":
      return formatInteger(value);
    case "decimal":
      return formatDecimal(value, decimals);
  }
}

export function MetricFormatter({
  value,
  format,
  decimals,
  currency,
  colorize = false,
  fallback = "—",
  className,
}: MetricFormatterProps) {
  if (value == null) {
    return <span className={cn("text-muted-foreground", className)}>{fallback}</span>;
  }

  const formatted = formatValue(value, format, decimals, currency);

  return (
    <span
      className={cn(
        colorize && value > 0 && "text-success",
        colorize && value < 0 && "text-danger",
        className,
      )}
    >
      {formatted}
    </span>
  );
}
