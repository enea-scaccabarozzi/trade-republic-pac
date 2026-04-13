import { Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface ChartContainerProps {
  title: string;
  description?: string;
  onLayersToggle?: () => void;
  layersOpen?: boolean;
  layersContent?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function ChartContainer({
  title,
  description,
  onLayersToggle,
  layersOpen,
  layersContent,
  children,
  className,
}: ChartContainerProps) {
  return (
    <div className={cn("rounded-lg border bg-card p-4", className)}>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">{title}</h3>
          {description && <p className="text-muted-foreground text-xs">{description}</p>}
        </div>
        {onLayersToggle && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={layersOpen ? "secondary" : "ghost"}
                  size="icon"
                  className="size-7"
                  onClick={onLayersToggle}
                >
                  <Layers className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Toggle overlays</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
      {layersOpen && layersContent && <div className="border-b pb-3 mb-3">{layersContent}</div>}
      <div className="w-full">{children}</div>
    </div>
  );
}
