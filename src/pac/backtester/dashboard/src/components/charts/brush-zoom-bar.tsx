import { RotateCcw } from "lucide-react";
import { Area, AreaChart, Brush, ResponsiveContainer } from "recharts";
import { Button } from "@/components/ui/button";
import type { BrushZoomState } from "@/hooks/use-brush-zoom";
import { cn } from "@/lib/utils";
import type { EquityCurvePoint } from "@/types/api";

export interface BrushZoomBarProps {
  equityCurve: EquityCurvePoint[];
  zoom: BrushZoomState;
  onBrushChange: (startIndex: number, endIndex: number) => void;
  onReset: () => void;
  isZoomed: boolean;
  className?: string;
}

export function BrushZoomBar({
  equityCurve,
  zoom,
  onBrushChange,
  onReset,
  isZoomed,
  className,
}: BrushZoomBarProps) {
  return (
    <div className={cn("relative rounded-lg border bg-card p-2", className)}>
      {isZoomed && (
        <Button
          variant="ghost"
          size="sm"
          className="absolute right-2 top-1 z-10 h-6 gap-1 px-2 text-xs"
          onClick={onReset}
        >
          <RotateCcw className="size-3" />
          Reset zoom
        </Button>
      )}
      <ResponsiveContainer width="100%" height={60}>
        <AreaChart data={equityCurve}>
          <Area
            type="monotone"
            dataKey="median"
            stroke="var(--color-chart-1)"
            fill="var(--color-chart-1)"
            fillOpacity={0.15}
            strokeWidth={1}
            dot={false}
            isAnimationActive={false}
          />
          <Brush
            dataKey="date"
            height={20}
            startIndex={zoom.startIndex}
            endIndex={zoom.endIndex}
            onChange={(e) => {
              if (e && typeof e.startIndex === "number" && typeof e.endIndex === "number") {
                onBrushChange(e.startIndex, e.endIndex);
              }
            }}
            stroke="var(--color-border)"
            fill="var(--color-muted)"
            travellerWidth={8}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
