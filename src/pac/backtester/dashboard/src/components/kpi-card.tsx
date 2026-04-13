import { TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string | number;
  description?: string;
  trend?: number;
  icon?: React.ComponentType<{ className?: string }>;
  children?: React.ReactNode;
  className?: string;
}

export function KpiCard({
  label,
  value,
  description,
  trend,
  icon: Icon,
  children,
  className,
}: KpiCardProps) {
  return (
    <Card className={cn("shadow-xs hover:shadow-sm transition-shadow", className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-muted-foreground text-sm font-medium">{label}</CardTitle>
        {Icon && <Icon className="text-muted-foreground size-4" />}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {(trend !== undefined || description) && (
          <div className="mt-1 flex items-center gap-1 text-xs">
            {trend !== undefined && (
              <>
                {trend >= 0 ? (
                  <TrendingUp className="text-success size-3" />
                ) : (
                  <TrendingDown className="text-danger size-3" />
                )}
                <span className={cn(trend >= 0 ? "text-success" : "text-danger")}>
                  {trend >= 0 ? "+" : ""}
                  {(trend * 100).toFixed(2)}%
                </span>
              </>
            )}
            {description && <span className="text-muted-foreground">{description}</span>}
          </div>
        )}
        {children}
      </CardContent>
    </Card>
  );
}
