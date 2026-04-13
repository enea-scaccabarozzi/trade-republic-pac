import { Search, X } from "lucide-react";
import { forwardRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface SearchToolbarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  children?: React.ReactNode;
  className?: string;
}

export const SearchToolbar = forwardRef<HTMLInputElement, SearchToolbarProps>(
  function SearchToolbar({ value, onChange, placeholder = "Search…", children, className }, ref) {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <div className="relative max-w-sm flex-1">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
          <Input
            ref={ref}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="pl-9 pr-8"
          />
          {value && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-1/2 right-1 size-6 -translate-y-1/2"
              onClick={() => onChange("")}
              aria-label="Clear search"
            >
              <X className="size-3.5" />
            </Button>
          )}
        </div>
        {children}
      </div>
    );
  },
);
