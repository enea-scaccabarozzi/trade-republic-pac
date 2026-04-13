import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  variant: "card" | "table" | "chart" | "page";
  rows?: number;
  className?: string;
}

export function LoadingSkeleton({ variant, rows = 5, className }: LoadingSkeletonProps) {
  switch (variant) {
    case "card":
      return (
        <div className={cn("space-y-3 rounded-lg border p-4", className)}>
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
      );
    case "table":
      return (
        <div className={cn("space-y-2", className)}>
          <Skeleton className="h-10 w-full" />
          {Array.from({ length: rows }, (_, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholders never reorder
            <Skeleton key={`skeleton-row-${i}`} className="h-8 w-full" />
          ))}
        </div>
      );
    case "chart":
      return (
        <div className={cn("space-y-3 rounded-lg border p-4", className)}>
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-7 w-7 rounded" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      );
    case "page":
      return (
        <div className={cn("space-y-6", className)}>
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholders never reorder
              <LoadingSkeleton key={`skeleton-card-${i}`} variant="card" />
            ))}
          </div>
          <LoadingSkeleton variant="table" rows={rows} />
        </div>
      );
  }
}
