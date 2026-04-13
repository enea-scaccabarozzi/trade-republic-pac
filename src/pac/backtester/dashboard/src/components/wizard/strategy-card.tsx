import { Check } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface StrategyCardProps {
  name: string;
  description: string;
  selected: boolean;
  onClick: () => void;
  className?: string;
}

function humanizeName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function StrategyCard({
  name,
  description,
  selected,
  onClick,
  className,
}: StrategyCardProps) {
  return (
    <Card
      className={cn(
        "relative cursor-pointer transition-all",
        selected
          ? "border-primary bg-primary/5 ring-2 ring-primary"
          : "border-border hover:shadow-sm",
        className,
      )}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      tabIndex={0}
      role="radio"
      aria-checked={selected}
    >
      <CardContent className="p-4">
        {selected && <Check className="absolute top-3 right-3 size-4 text-primary" />}
        <h3 className="text-base font-semibold">{humanizeName(name)}</h3>
        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}
