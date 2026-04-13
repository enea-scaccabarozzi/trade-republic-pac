import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface DateRange {
  from: string | null;
  to: string | null;
}

interface DateRangeFilterProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  minDate?: string;
  maxDate?: string;
  className?: string;
}

export function DateRangeFilter({
  value,
  onChange,
  minDate,
  maxDate,
  className,
}: DateRangeFilterProps) {
  const hasValue = value.from !== null || value.to !== null;

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <label htmlFor="date-range-from" className="text-muted-foreground text-sm">
        From
      </label>
      <Input
        id="date-range-from"
        type="date"
        value={value.from ?? ""}
        onChange={(e) => onChange({ ...value, from: e.target.value || null })}
        min={minDate}
        max={value.to ?? maxDate}
        className="w-auto"
      />
      <label htmlFor="date-range-to" className="text-muted-foreground text-sm">
        To
      </label>
      <Input
        id="date-range-to"
        type="date"
        value={value.to ?? ""}
        onChange={(e) => onChange({ ...value, to: e.target.value || null })}
        min={value.from ?? minDate}
        max={maxDate}
        className="w-auto"
      />
      {hasValue && (
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={() => onChange({ from: null, to: null })}
          aria-label="Clear date range"
        >
          <X className="size-3.5" />
        </Button>
      )}
    </div>
  );
}
