import { GitCompareArrows, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface BatchActionBarProps {
  selectedCount: number;
  onCompare: () => void;
  onDelete: () => void;
  onClearSelection: () => void;
  children?: React.ReactNode;
  className?: string;
}

export function BatchActionBar({
  selectedCount,
  onCompare,
  onDelete,
  onClearSelection,
  children,
  className,
}: BatchActionBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className={cn("bg-muted flex items-center gap-3 rounded-lg px-4 py-2", className)}>
      {children ?? (
        <span className="text-sm font-medium">
          {selectedCount} {selectedCount === 1 ? "run" : "runs"} selected
        </span>
      )}
      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" onClick={onCompare} disabled={selectedCount < 2}>
          <GitCompareArrows className="mr-1.5 size-4" />
          Compare
        </Button>
        <Button variant="destructive" size="sm" onClick={onDelete}>
          <Trash2 className="mr-1.5 size-4" />
          Delete
        </Button>
        <Button variant="ghost" size="sm" onClick={onClearSelection}>
          <X className="mr-1.5 size-4" />
          Clear
        </Button>
      </div>
    </div>
  );
}
