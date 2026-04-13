import { ChartContainer } from "@/components/chart-container";
import { StrategyEventTimeline } from "@/components/charts/strategy-event-timeline";
import { RuleActivitySummary } from "@/components/run-detail/rule-activity-summary";
import { SignalActivityLog } from "@/components/run-detail/signal-activity-log";
import type { RunResult } from "@/types/api";

interface SignalsTabProps {
  run: RunResult;
}

export function SignalsTab({ run }: SignalsTabProps) {
  return (
    <div className="flex flex-col gap-6">
      {run.signal_log.length > 0 && (
        <RuleActivitySummary
          signalLog={run.signal_log}
          startDate={run.config.start_date}
          endDate={run.config.end_date}
        />
      )}
      <SignalActivityLog signalLog={run.signal_log} />
      <ChartContainer
        title="Strategy Event Timeline"
        description="Event history across the backtest period"
      >
        <StrategyEventTimeline
          events={run.strategy_events}
          eventMeta={run.strategy_event_meta}
          startDate={run.config.start_date}
          endDate={run.config.end_date}
        />
      </ChartContainer>
    </div>
  );
}
