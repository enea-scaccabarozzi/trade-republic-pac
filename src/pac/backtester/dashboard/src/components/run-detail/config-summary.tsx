import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { StatBadge } from "@/components/stat-badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BacktestConfig, MonteCarloInfo } from "@/types/api";

export interface ConfigSummaryProps {
  config: BacktestConfig;
  monteCarlo: MonteCarloInfo;
  className?: string;
}

export function ConfigSummary({ config, monteCarlo, className }: ConfigSummaryProps) {
  const [open, setOpen] = useState(false);

  const hasStrategyParams =
    config.strategy_params && Object.keys(config.strategy_params).length > 0;

  return (
    <Collapsible open={open} onOpenChange={setOpen} className={cn("rounded-lg border", className)}>
      <CollapsibleTrigger className="flex w-full items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors">
        <span className="text-sm font-medium">Configuration</span>
        <ChevronDown
          className={cn("text-muted-foreground size-4 transition-transform", open && "rotate-180")}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4">
        <div className="flex flex-wrap gap-2 pt-2">
          <StatBadge label="Strategy" value={config.strategy} />
          <StatBadge label="Date Range" value={`${config.start_date} – ${config.end_date}`} />
          <StatBadge label="Initial Cash" value={formatCurrency(config.initial_cash)} />
          <StatBadge label="Monthly" value={formatCurrency(config.monthly_contribution)} />
          <StatBadge label="PAC Days" value={config.pac_execution_days.join(", ")} />
          <StatBadge label="Settlement Fee" value={formatCurrency(config.settlement_fee)} />
          <StatBadge label="Spread" value={`${config.spread_bps} bps`} />
          <StatBadge
            label="Slippage"
            value={`${config.slippage_days[0]}–${config.slippage_days[1]} days`}
          />
          <StatBadge label="MC Iterations" value={monteCarlo.iterations} />
          <StatBadge
            label="Benchmark"
            value={config.benchmark ? "Enabled" : "Disabled"}
            variant={config.benchmark ? "info" : "neutral"}
          />
        </div>
        {hasStrategyParams && (
          <div className="mt-3">
            <p className="text-muted-foreground mb-1 text-xs font-medium">Strategy Parameters</p>
            <pre className="rounded-md bg-muted p-3 text-xs font-mono overflow-x-auto">
              {JSON.stringify(config.strategy_params, null, 2)}
            </pre>
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
