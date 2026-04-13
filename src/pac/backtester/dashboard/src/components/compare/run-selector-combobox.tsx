import { Check, ChevronsUpDown, X } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatPercent } from "@/lib/format";
import { CHART_COLORS } from "@/lib/run-colors";
import { cn } from "@/lib/utils";
import type { RunSummary } from "@/types/api";

export interface RunSelectorComboboxProps {
  runs: RunSummary[];
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  maxSelections?: number;
  className?: string;
}

export function RunSelectorCombobox({
  runs,
  selectedIds,
  onSelectionChange,
  maxSelections = 6,
  className,
}: RunSelectorComboboxProps) {
  const [open, setOpen] = useState(false);
  const atLimit = selectedIds.length >= maxSelections;

  const toggle = (runId: string) => {
    if (selectedIds.includes(runId)) {
      onSelectionChange(selectedIds.filter((id) => id !== runId));
    } else if (!atLimit) {
      onSelectionChange([...selectedIds, runId]);
    }
  };

  const deselect = (runId: string) => {
    onSelectionChange(selectedIds.filter((id) => id !== runId));
  };

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" className="w-[320px] justify-between">
              {selectedIds.length === 0
                ? "Select runs to compare..."
                : `${selectedIds.length} run${selectedIds.length > 1 ? "s" : ""} selected`}
              <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[420px] p-0" align="start">
            <Command>
              <CommandInput placeholder="Search by strategy or run ID..." />
              <CommandList>
                <CommandEmpty>No runs found.</CommandEmpty>
                <CommandGroup>
                  {runs.map((run) => {
                    const isSelected = selectedIds.includes(run.run_id);
                    const isDisabled = atLimit && !isSelected;
                    return (
                      <CommandItem
                        key={run.run_id}
                        value={`${run.strategy} ${run.run_id}`}
                        onSelect={() => toggle(run.run_id)}
                        disabled={isDisabled}
                        className={cn(isDisabled && "opacity-50")}
                      >
                        <Check
                          className={cn("mr-2 size-4", isSelected ? "opacity-100" : "opacity-0")}
                        />
                        <div className="flex flex-1 items-center justify-between gap-2">
                          <div className="min-w-0">
                            <span className="font-medium">{run.strategy}</span>
                            <span className="text-muted-foreground ml-1.5 text-xs">
                              ({run.run_id.slice(0, 8)})
                            </span>
                            <div className="text-muted-foreground text-xs">
                              {run.start_date.slice(0, 7)} – {run.end_date.slice(0, 7)}
                            </div>
                          </div>
                          {run.cagr_median != null && (
                            <span className="text-xs tabular-nums">
                              {formatPercent(run.cagr_median)}
                            </span>
                          )}
                        </div>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
        {selectedIds.length > 0 && (
          <Button variant="ghost" size="sm" onClick={() => onSelectionChange([])}>
            Clear all
          </Button>
        )}
      </div>
      {selectedIds.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedIds.map((id, i) => {
            const run = runs.find((r) => r.run_id === id);
            return (
              <Badge
                key={id}
                variant="secondary"
                className="gap-1 text-xs"
                style={{ borderLeftColor: CHART_COLORS[i], borderLeftWidth: 3 }}
              >
                {run ? `${run.strategy} (${id.slice(0, 8)})` : id.slice(0, 8)}
                <X className="size-3 cursor-pointer" onClick={() => deselect(id)} />
              </Badge>
            );
          })}
        </div>
      )}
    </div>
  );
}
