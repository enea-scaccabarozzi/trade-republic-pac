import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import type { WizardFormValues } from "@/components/wizard/review-step";
import { cn } from "@/lib/utils";

export interface ConfigStepProps {
  values: WizardFormValues;
  onChange: <K extends keyof WizardFormValues>(name: K, value: WizardFormValues[K]) => void;
  className?: string;
}

function FieldWrapper({
  label,
  htmlFor,
  description,
  children,
}: {
  label: string;
  htmlFor: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
    </div>
  );
}

export function ConfigStep({ values, onChange, className }: ConfigStepProps) {
  return (
    <div className={cn("space-y-8", className)}>
      {/* Group 1: Date Range */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Backtest Period</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FieldWrapper label="Start Date" htmlFor="startDate">
            <Input
              id="startDate"
              type="date"
              value={values.startDate}
              onChange={(e) => onChange("startDate", e.target.value)}
            />
          </FieldWrapper>
          <FieldWrapper label="End Date" htmlFor="endDate">
            <Input
              id="endDate"
              type="date"
              value={values.endDate}
              onChange={(e) => onChange("endDate", e.target.value)}
            />
          </FieldWrapper>
        </div>
      </div>

      {/* Group 2: Financial Parameters */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Financial Settings</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FieldWrapper
            label="Initial Cash (EUR)"
            htmlFor="initialCash"
            description="Starting portfolio value"
          >
            <Input
              id="initialCash"
              type="number"
              min={0}
              step="any"
              value={values.initialCash}
              onChange={(e) => onChange("initialCash", Number(e.target.value))}
            />
          </FieldWrapper>

          <FieldWrapper
            label="Monthly Contribution (EUR)"
            htmlFor="monthlyContribution"
            description="Monthly PAC contribution"
          >
            <Input
              id="monthlyContribution"
              type="number"
              min={0}
              step="any"
              value={values.monthlyContribution}
              onChange={(e) => onChange("monthlyContribution", Number(e.target.value))}
            />
          </FieldWrapper>

          <FieldWrapper
            label="PAC Execution Days"
            htmlFor="pacExecutionDays"
            description="Comma-separated days of month (1-28)"
          >
            <Input
              id="pacExecutionDays"
              type="text"
              value={values.pacExecutionDays}
              onChange={(e) => onChange("pacExecutionDays", e.target.value)}
              placeholder="2, 16"
            />
          </FieldWrapper>

          <FieldWrapper
            label="Settlement Fee (EUR)"
            htmlFor="settlementFee"
            description="Per-trade settlement fee"
          >
            <Input
              id="settlementFee"
              type="number"
              min={0}
              step="any"
              value={values.settlementFee}
              onChange={(e) => onChange("settlementFee", Number(e.target.value))}
            />
          </FieldWrapper>

          <FieldWrapper
            label="Spread (basis points)"
            htmlFor="spreadBps"
            description="Bid-ask spread in basis points"
          >
            <Input
              id="spreadBps"
              type="number"
              min={0}
              step="1"
              value={values.spreadBps}
              onChange={(e) => onChange("spreadBps", Number(e.target.value))}
            />
          </FieldWrapper>

          <FieldWrapper
            label="Min Slippage (days)"
            htmlFor="slippageMin"
            description="Minimum human delay days"
          >
            <Input
              id="slippageMin"
              type="number"
              min={0}
              step="1"
              value={values.slippageMin}
              onChange={(e) => onChange("slippageMin", Number(e.target.value))}
            />
          </FieldWrapper>

          <FieldWrapper
            label="Max Slippage (days)"
            htmlFor="slippageMax"
            description="Maximum human delay days"
          >
            <Input
              id="slippageMax"
              type="number"
              min={0}
              step="1"
              value={values.slippageMax}
              onChange={(e) => onChange("slippageMax", Number(e.target.value))}
            />
          </FieldWrapper>
        </div>
      </div>

      {/* Group 3: Monte Carlo */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Monte Carlo</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FieldWrapper
            label="Iterations"
            htmlFor="monteCarloIterations"
            description="Number of Monte Carlo iterations"
          >
            <div className="flex items-center gap-4">
              <Slider
                min={10}
                max={1000}
                step={10}
                value={[values.monteCarloIterations]}
                onValueChange={([v]) => {
                  if (v !== undefined) onChange("monteCarloIterations", v);
                }}
                className="flex-1"
              />
              <Input
                id="monteCarloIterations"
                type="number"
                min={1}
                step="1"
                value={values.monteCarloIterations}
                onChange={(e) => onChange("monteCarloIterations", Number(e.target.value))}
                className="w-24"
              />
            </div>
          </FieldWrapper>

          <div className="flex items-center gap-3 pt-6">
            <Switch
              id="benchmark"
              checked={values.benchmark}
              onCheckedChange={(checked) => onChange("benchmark", checked)}
            />
            <Label htmlFor="benchmark">Compare against buy-and-hold benchmark</Label>
          </div>
        </div>
      </div>
    </div>
  );
}
