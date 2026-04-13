import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { formatDecimal, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

interface TrendIndicatorProps {
  value: number;
  format?: "percent" | "absolute";
  invertColor?: boolean;
  className?: string;
}

export function TrendIndicator({
  value,
  format = "percent",
  invertColor = false,
  className,
}: TrendIndicatorProps) {
  const isPositive = value > 0;
  const isNegative = value < 0;
  const isNeutral = value === 0;

  const colorPositive = invertColor ? "text-danger" : "text-success";
  const colorNegative = invertColor ? "text-success" : "text-danger";

  const formatted =
    format === "percent"
      ? `${isPositive ? "+" : ""}${formatPercent(value)}`
      : `${isPositive ? "+" : ""}${formatDecimal(value)}`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-sm font-medium",
        isPositive && colorPositive,
        isNegative && colorNegative,
        isNeutral && "text-muted-foreground",
        className,
      )}
    >
      {isPositive && <TrendingUp className="size-3.5" />}
      {isNegative && <TrendingDown className="size-3.5" />}
      {isNeutral && <Minus className="size-3.5" />}
      {formatted}
    </span>
  );
}
