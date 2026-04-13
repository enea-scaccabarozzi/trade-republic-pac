import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { z } from "zod";
import { LoadingSkeleton } from "@/components/loading-skeleton";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ConfigStep } from "@/components/wizard/config-step";
import { ProgressView } from "@/components/wizard/progress-view";
import { ReviewStep, type WizardFormValues } from "@/components/wizard/review-step";
import { StrategyPicker } from "@/components/wizard/strategy-picker";
import { type WizardStep, WizardStepper } from "@/components/wizard/wizard-stepper";
import { useRunDetail } from "@/hooks/use-run-detail";
import { useRunProgress } from "@/hooks/use-run-progress";
import { useStartBacktest } from "@/hooks/use-start-backtest";
import { useStrategies } from "@/hooks/use-strategies";
import { jsonSchemaToZod } from "@/lib/schema-to-zod";
import type { RunDetailResponse, StartBacktestConfig, StrategyInfo } from "@/types/api";

const searchSchema = z.object({
  clone: z.string().optional(),
});

export const Route = createFileRoute("/run")({
  validateSearch: searchSchema,
  component: RunBacktest,
});

const STEPS: WizardStep[] = [
  { label: "Strategy", description: "Pick a strategy" },
  { label: "Configure", description: "Set parameters" },
  { label: "Review", description: "Confirm & launch" },
];

const DEFAULT_VALUES: WizardFormValues = {
  strategy: "",
  strategyParams: {},
  startDate: "2000-01-01",
  endDate: new Date().toISOString().slice(0, 10),
  initialCash: 10000,
  monthlyContribution: 200,
  pacExecutionDays: "2, 16",
  settlementFee: 1,
  spreadBps: 10,
  slippageMin: 0,
  slippageMax: 2,
  monteCarloIterations: 100,
  benchmark: true,
};

function parsePacDays(raw: string): number[] {
  return raw
    .split(",")
    .map((s) => Number.parseInt(s.trim(), 10))
    .filter((n) => !Number.isNaN(n) && n >= 1 && n <= 28);
}

function configToFormValues(response: RunDetailResponse): WizardFormValues {
  const c = response.run.config;
  return {
    strategy: c.strategy,
    strategyParams: c.strategy_params,
    startDate: c.start_date,
    endDate: c.end_date,
    initialCash: c.initial_cash,
    monthlyContribution: c.monthly_contribution,
    pacExecutionDays: c.pac_execution_days.join(", "),
    settlementFee: c.settlement_fee,
    spreadBps: c.spread_bps,
    slippageMin: c.slippage_days[0],
    slippageMax: c.slippage_days[1],
    monteCarloIterations: c.monte_carlo_iterations,
    benchmark: c.benchmark,
  };
}

function buildStartConfig(values: WizardFormValues): StartBacktestConfig {
  return {
    strategy: values.strategy,
    strategy_params: values.strategyParams,
    start_date: values.startDate,
    end_date: values.endDate,
    initial_cash: values.initialCash,
    monthly_contribution: values.monthlyContribution,
    pac_execution_days: parsePacDays(values.pacExecutionDays),
    settlement_fee: values.settlementFee,
    spread_bps: values.spreadBps,
    slippage_days: [values.slippageMin, values.slippageMax],
    monte_carlo_iterations: values.monteCarloIterations,
    benchmark: values.benchmark,
  };
}

function validateConfigStep(values: WizardFormValues): string | null {
  if (values.endDate <= values.startDate) {
    return "End date must be after start date.";
  }
  if (values.slippageMax < values.slippageMin) {
    return "Slippage max must be ≥ slippage min.";
  }
  const days = parsePacDays(values.pacExecutionDays);
  if (days.length === 0) {
    return "At least one PAC execution day (1-28) is required.";
  }
  if (values.initialCash <= 0) {
    return "Initial cash must be positive.";
  }
  if (values.monthlyContribution < 0) {
    return "Monthly contribution cannot be negative.";
  }
  if (values.monteCarloIterations < 1) {
    return "At least 1 Monte Carlo iteration is required.";
  }
  return null;
}

function useWizardForm(initialValues: WizardFormValues, strategies: StrategyInfo[]) {
  const [values, setValues] = useState<WizardFormValues>(initialValues);

  const updateField = useCallback(
    <K extends keyof WizardFormValues>(name: K, value: WizardFormValues[K]) => {
      setValues((prev) => ({ ...prev, [name]: value }));
    },
    [],
  );

  const updateStrategyParam = useCallback((key: string, value: unknown) => {
    setValues((prev) => ({
      ...prev,
      strategyParams: { ...prev.strategyParams, [key]: value },
    }));
  }, []);

  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(
    initialValues.strategy || null,
  );

  const schemaResult = useMemo(() => {
    if (!selectedStrategy) return null;
    const info = strategies.find((s) => s.name === selectedStrategy);
    if (!info?.params_schema) return null;
    return jsonSchemaToZod(info.params_schema);
  }, [selectedStrategy, strategies]);

  const handleSelectStrategy = useCallback(
    (name: string) => {
      setSelectedStrategy(name);
      updateField("strategy", name);
      const info = strategies.find((s) => s.name === name);
      if (info?.params_schema) {
        const result = jsonSchemaToZod(info.params_schema);
        updateField("strategyParams", result.defaults);
      } else {
        updateField("strategyParams", {});
      }
    },
    [strategies, updateField],
  );

  const strategyDescription = useMemo(() => {
    const info = strategies.find((s) => s.name === values.strategy);
    return info?.description ?? "";
  }, [strategies, values.strategy]);

  return {
    values,
    updateField,
    updateStrategyParam,
    selectedStrategy,
    schemaResult,
    handleSelectStrategy,
    strategyDescription,
  };
}

interface StepContentProps {
  step: number;
  strategies: StrategyInfo[];
  selectedStrategy: string | null;
  onSelectStrategy: (name: string) => void;
  values: WizardFormValues;
  updateField: <K extends keyof WizardFormValues>(name: K, value: WizardFormValues[K]) => void;
  updateStrategyParam: (key: string, value: unknown) => void;
  schemaResult: ReturnType<typeof jsonSchemaToZod> | null;
  validationError: string | null;
  strategyDescription: string;
  onLaunch: () => void;
  isSubmitting: boolean;
  submitError: string | null;
}

function StepContent({
  step,
  strategies,
  selectedStrategy,
  onSelectStrategy,
  values,
  updateField,
  updateStrategyParam,
  schemaResult,
  validationError,
  strategyDescription,
  onLaunch,
  isSubmitting,
  submitError,
}: StepContentProps) {
  if (step === 0) {
    return (
      <StrategyPicker
        strategies={strategies}
        selectedStrategy={selectedStrategy}
        onSelectStrategy={onSelectStrategy}
        strategyParams={values.strategyParams}
        onParamChange={updateStrategyParam}
        schemaFields={schemaResult?.fields ?? null}
      />
    );
  }
  if (step === 1) {
    return (
      <div className="space-y-4">
        <ConfigStep values={values} onChange={updateField} />
        {validationError && (
          <p className="text-sm font-medium text-destructive">{validationError}</p>
        )}
      </div>
    );
  }
  if (step === 2) {
    return (
      <ReviewStep
        values={values}
        strategyDescription={strategyDescription}
        schemaFields={schemaResult?.fields ?? null}
        onLaunch={onLaunch}
        isSubmitting={isSubmitting}
        submitError={submitError}
      />
    );
  }
  return null;
}

function RunBacktest() {
  const { clone } = Route.useSearch();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  const { data: strategiesData } = useStrategies();
  const { data: cloneData, isPending: clonePending } = useRunDetail(clone ?? "");
  const strategies = strategiesData?.strategies ?? [];

  const cloneDefaults = useMemo<WizardFormValues | null>(
    () => (cloneData ? configToFormValues(cloneData) : null),
    [cloneData],
  );

  const isLoadingClone = !!clone && clonePending;

  const initialValues = cloneDefaults ?? DEFAULT_VALUES;

  const {
    values,
    updateField,
    updateStrategyParam,
    selectedStrategy,
    schemaResult,
    handleSelectStrategy,
    strategyDescription,
  } = useWizardForm(initialValues, strategies);

  const startBacktest = useStartBacktest();
  const [jobId, setJobId] = useState<string | null>(null);
  const { progress, reset: resetProgress } = useRunProgress(jobId);

  const [validationError, setValidationError] = useState<string | null>(null);

  const handleNext = useCallback(() => {
    if (step === 1) {
      const error = validateConfigStep(values);
      if (error) {
        setValidationError(error);
        return;
      }
    }
    setValidationError(null);
    setStep((s) => s + 1);
  }, [step, values]);

  const canAdvance = step === 0 ? !!selectedStrategy : true;

  const handleLaunch = useCallback(() => {
    startBacktest.mutate(
      { config: buildStartConfig(values) },
      {
        onSuccess: (data) => {
          setJobId(data.run_id);
          setStep(3);
        },
      },
    );
  }, [values, startBacktest]);

  const handleComplete = useCallback(
    (runId: string) => {
      navigate({ to: "/runs/$id", params: { id: runId } });
    },
    [navigate],
  );

  const handleRetry = useCallback(() => {
    setJobId(null);
    resetProgress();
    setStep(2);
  }, [resetProgress]);

  if (isLoadingClone) {
    return (
      <div className="space-y-6">
        <PageHeader title="Run Backtest" description="Loading configuration…" />
        <LoadingSkeleton variant="page" />
      </div>
    );
  }

  if (step === 3 && progress) {
    return (
      <div className="mx-auto max-w-2xl py-8">
        <ProgressView progress={progress} onComplete={handleComplete} onError={handleRetry} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Run Backtest" description="Configure and launch a new backtest" />
      <WizardStepper steps={STEPS} currentStep={Math.min(step, 2)} />

      <div className="min-h-[400px]">
        <StepContent
          step={step}
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          onSelectStrategy={handleSelectStrategy}
          values={values}
          updateField={updateField}
          updateStrategyParam={updateStrategyParam}
          schemaResult={schemaResult}
          validationError={validationError}
          strategyDescription={strategyDescription}
          onLaunch={handleLaunch}
          isSubmitting={startBacktest.isPending}
          submitError={
            startBacktest.isError ? (startBacktest.error?.message ?? "Launch failed") : null
          }
        />
      </div>

      {step < 3 && (
        <div className="flex justify-between border-t pt-4">
          <Button variant="outline" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
            <ArrowLeft className="mr-2 size-4" />
            Back
          </Button>
          {step < 2 && (
            <Button disabled={!canAdvance} onClick={handleNext}>
              Next
              <ArrowRight className="ml-2 size-4" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
