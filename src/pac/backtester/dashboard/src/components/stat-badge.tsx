import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface StatBadgeProps {
  label: string;
  value: string | number;
  variant?: "success" | "warning" | "danger" | "info" | "neutral";
  className?: string;
}

const variantStyles: Record<string, string> = {
  success: "bg-success/10 text-success border-success/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  danger: "bg-danger/10 text-danger border-danger/20",
  info: "bg-info/10 text-info border-info/20",
  neutral: "bg-muted text-muted-foreground border-border",
};

export function StatBadge({ label, value, variant = "neutral", className }: StatBadgeProps) {
  return (
    <Badge variant="outline" className={cn(variantStyles[variant], className)}>
      <span className="mr-1 font-normal">{label}</span>
      <span className="font-semibold">{value}</span>
    </Badge>
  );
}
