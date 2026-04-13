import { Loader2, Play } from "lucide-react";
import { StatBadge } from "@/components/stat-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency } from "@/lib/format";
import type { FieldMeta } from "@/lib/schema-to-zod";
import { cn } from "@/lib/utils";

export interface WizardFormValues {
  strategy: string;
  strategyParams: Record<string, unknown>;
  startDate: string;
  endDate: string;
  initialCash: number;
  monthlyContribution: number;
  pacExecutionDays: string;
  settlementFee: number;
  spreadBps: number;
  slippageMin: number;
  slippageMax: number;
  monteCarloIterations: number;
  benchmark: boolean;
}

export interface ReviewStepProps {
  values: WizardFormValues;
  strategyDescription: string;
  schemaFields: FieldMeta[] | null;
  onLaunch: () => void;
  isSubmitting: boolean;
  submitError: string | null;
  className?: string;
}

function humanizeName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatParamValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  return String(value ?? "—");
}

export function ReviewStep({
  values,
  strategyDescription,
  schemaFields,
  onLaunch,
  isSubmitting,
  submitError,
  className,
}: ReviewStepProps) {
  return (
    <div className={cn("space-y-6", className)}>
      {/* Section 1: Strategy */}
      <Card>
        <CardHeader>
          <CardTitle>{humanizeName(values.strategy)}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{strategyDescription}</p>
          {schemaFields && schemaFields.length > 0 && (
            <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {schemaFields.map((field) => {
                const val = values.strategyParams[field.key];
                const isDefault = val === field.defaultValue;
                return (
                  <div
                    key={field.key}
                    className="flex justify-between gap-2 rounded-md bg-muted/50 px-3 py-2"
                  >
                    <dt className="text-sm font-medium">{field.label}</dt>
                    <dd
                      className={cn(
                        "text-sm",
                        isDefault ? "text-muted-foreground" : "font-semibold",
                      )}
                    >
                      {formatParamValue(val)}
                    </dd>
                  </div>
                );
              })}
            </dl>
          )}
        </CardContent>
      </Card>

      {/* Section 2: Configuration */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">Configuration</h3>
        <div className="flex flex-wrap gap-2">
          <StatBadge
            label="Period"
            value={`${values.startDate} – ${values.endDate}`}
            variant="info"
          />
          <StatBadge label="Initial Cash" value={formatCurrency(values.initialCash)} />
          <StatBadge label="Monthly" value={`${formatCurrency(values.monthlyContribution)}/mo`} />
          <StatBadge label="PAC Days" value={values.pacExecutionDays} />
          <StatBadge
            label="Fees"
            value={`${formatCurrency(values.settlementFee)} + ${values.spreadBps}bps`}
          />
          <StatBadge label="Slippage" value={`${values.slippageMin}–${values.slippageMax} days`} />
        </div>
      </div>

      {/* Section 3: Simulation */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">Simulation</h3>
        <div className="flex flex-wrap gap-2">
          <StatBadge
            label="Iterations"
            value={`${values.monteCarloIterations} iterations`}
            variant="info"
          />
          <StatBadge label="Benchmark" value={values.benchmark ? "Enabled" : "Disabled"} />
        </div>
      </div>

      {/* Launch Button */}
      <div className="pt-2">
        <Button size="lg" onClick={onLaunch} disabled={isSubmitting} className="w-full sm:w-auto">
          {isSubmitting ? (
            <Loader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <Play className="mr-2 size-4" />
          )}
          Launch Backtest
        </Button>
        {submitError && <p className="mt-2 text-sm text-destructive">{submitError}</p>}
      </div>
    </div>
  );
}
