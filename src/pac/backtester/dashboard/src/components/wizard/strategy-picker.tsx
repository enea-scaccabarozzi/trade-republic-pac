import { SchemaForm } from "@/components/wizard/schema-form";
import { StrategyCard } from "@/components/wizard/strategy-card";
import type { FieldMeta } from "@/lib/schema-to-zod";
import { cn } from "@/lib/utils";
import type { StrategyInfo } from "@/types/api";

export interface StrategyPickerProps {
  strategies: StrategyInfo[];
  selectedStrategy: string | null;
  onSelectStrategy: (name: string) => void;
  strategyParams: Record<string, unknown>;
  onParamChange: (key: string, value: unknown) => void;
  schemaFields: FieldMeta[] | null;
  className?: string;
}

export function StrategyPicker({
  strategies,
  selectedStrategy,
  onSelectStrategy,
  strategyParams,
  onParamChange,
  schemaFields,
  className,
}: StrategyPickerProps) {
  return (
    <div className={cn("space-y-6", className)}>
      <div>
        <h2 className="text-lg font-semibold">Choose a Strategy</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Select a backtest strategy and configure its parameters.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {strategies.map((info) => (
          <StrategyCard
            key={info.name}
            name={info.name}
            description={info.description}
            selected={info.name === selectedStrategy}
            onClick={() => onSelectStrategy(info.name)}
          />
        ))}
      </div>

      {selectedStrategy && schemaFields && (
        <div className="space-y-4 rounded-lg border p-4">
          <h3 className="font-semibold">Strategy Parameters</h3>
          <SchemaForm fields={schemaFields} values={strategyParams} onParamChange={onParamChange} />
        </div>
      )}
    </div>
  );
}
