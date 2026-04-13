import { useMemo } from "react";
import { AllocationChart } from "@/components/charts/allocation-chart";
import { BrushZoomBar } from "@/components/charts/brush-zoom-bar";
import { DrawdownChart } from "@/components/charts/drawdown-chart";
import { EquityChart } from "@/components/charts/equity-chart";
import { useBrushZoom } from "@/hooks/use-brush-zoom";
import type { RunResult } from "@/types/api";

export interface ChartsTabProps {
  run: RunResult;
}

export function ChartsTab({ run }: ChartsTabProps) {
  const { zoom, handleBrushChange, resetZoom, isZoomed } = useBrushZoom(run.equity_curve.length);

  const zoomedEquity = useMemo(
    () => run.equity_curve.slice(zoom.startIndex, zoom.endIndex + 1),
    [run.equity_curve, zoom],
  );

  const zoomedBenchmark = useMemo(
    () => run.benchmark_equity_curve?.slice(zoom.startIndex, zoom.endIndex + 1) ?? null,
    [run.benchmark_equity_curve, zoom],
  );

  const zoomedAllocations = useMemo(() => {
    const startDate = run.equity_curve[zoom.startIndex]?.date;
    const endDate = run.equity_curve[zoom.endIndex]?.date;
    if (!startDate || !endDate) return run.allocations;
    return run.allocations.filter((a) => a.date >= startDate && a.date <= endDate);
  }, [run.allocations, run.equity_curve, zoom]);

  return (
    <div className="flex flex-col gap-4">
      <BrushZoomBar
        equityCurve={run.equity_curve}
        zoom={zoom}
        onBrushChange={handleBrushChange}
        onReset={resetZoom}
        isZoomed={isZoomed}
      />

      <EquityChart
        equityCurve={zoomedEquity}
        benchmarkEquityCurve={zoomedBenchmark}
        indicatorSeries={run.indicator_series}
        strategyEvents={run.strategy_events}
        strategyEventMeta={run.strategy_event_meta}
      />

      <AllocationChart allocations={zoomedAllocations} />

      <DrawdownChart
        equityCurve={zoomedEquity}
        indicatorSeries={run.indicator_series}
        strategyEvents={run.strategy_events}
        strategyEventMeta={run.strategy_event_meta}
      />
    </div>
  );
}
