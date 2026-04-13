import { Fragment, useMemo } from "react";
import { Line, ReferenceArea, ReferenceLine, YAxis } from "recharts";
import type { ChartType } from "@/components/overlay-panel";
import { useOverlayStore } from "@/stores/overlay-store";
import type { IndicatorSeries, StrategyEvent, StrategyEventMeta } from "@/types/api";

export interface OverlayRendererProps {
  chartType: ChartType;
  indicatorSeries: IndicatorSeries[];
  strategyEvents: StrategyEvent[];
  strategyEventMeta: StrategyEventMeta[];
  dateRange: string[];
}

const OVERLAY_COLORS = [
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
  "var(--color-chart-7)",
  "var(--color-chart-8)",
];

interface BooleanSpan {
  start: string;
  end: string;
}

function computeBooleanSpans(
  data: { date: string; value: number | boolean | null }[],
  dateRange: string[],
): BooleanSpan[] {
  const dateSet = new Set(dateRange);
  const filtered = data.filter((d) => dateSet.has(d.date) && d.value === true);
  if (filtered.length === 0) return [];

  const first = filtered[0];
  if (!first) return [];

  const spans: BooleanSpan[] = [];
  let start = first.date;
  let prev = start;

  for (let i = 1; i < filtered.length; i++) {
    const entry = filtered[i];
    if (!entry) continue;
    const cur = entry.date;
    const prevIdx = dateRange.indexOf(prev);
    const curIdx = dateRange.indexOf(cur);
    if (curIdx - prevIdx > 1) {
      spans.push({ start, end: prev });
      start = cur;
    }
    prev = cur;
  }
  spans.push({ start, end: prev });
  return spans;
}

interface OverlayAccumulator {
  result: React.ReactElement[];
  colorIdx: number;
  needsSecondaryAxis: boolean;
}

function buildContinuousOverlay(
  series: IndicatorSeries,
  dateRange: string[],
  color: string,
): React.ReactElement[] {
  const elements: React.ReactElement[] = [];
  const lookup = new Map(
    series.data
      .filter((d) => d.value != null && typeof d.value === "number")
      .map((d) => [d.date, d.value as number]),
  );
  const overlayData = dateRange.map((date) => ({
    date,
    [series.meta.key]: lookup.get(date) ?? null,
  }));

  elements.push(
    <Line
      key={`overlay-line-${series.meta.key}`}
      data={overlayData}
      dataKey={series.meta.key}
      yAxisId="overlay"
      stroke={color}
      strokeWidth={1.5}
      strokeDasharray="4 4"
      dot={false}
      connectNulls
    />,
  );

  for (const threshold of series.meta.thresholds) {
    elements.push(
      <ReferenceLine
        key={`threshold-${series.meta.key}-${threshold.value}`}
        yAxisId="overlay"
        y={threshold.value}
        stroke={threshold.color || color}
        strokeDasharray="2 2"
        strokeOpacity={0.5}
        label={{
          value: threshold.label,
          position: "right",
          fill: "var(--color-muted-foreground)",
          fontSize: 10,
        }}
      />,
    );
  }
  return elements;
}

function buildBooleanOverlay(
  series: IndicatorSeries,
  dateRange: string[],
  color: string,
): React.ReactElement[] {
  const spans = computeBooleanSpans(series.data, dateRange);
  return spans.map((span) => (
    <ReferenceArea
      key={`bool-span-${series.meta.key}-${span.start}`}
      x1={span.start}
      x2={span.end}
      fill={color}
      fillOpacity={0.08}
      strokeOpacity={0}
    />
  ));
}

function buildRatioOverlay(
  series: IndicatorSeries,
  indicatorSeries: IndicatorSeries[],
  dateRange: string[],
  acc: OverlayAccumulator,
): React.ReactElement[] {
  const elements: React.ReactElement[] = [];
  const allKeys = [series.meta.key, ...series.meta.companion_keys];
  for (const rk of allKeys) {
    const companionSeries =
      rk === series.meta.key ? series : indicatorSeries.find((s) => s.meta.key === rk);
    if (!companionSeries) continue;

    const lookup = new Map(
      companionSeries.data
        .filter((d) => d.value != null && typeof d.value === "number")
        .map((d) => [d.date, d.value as number]),
    );
    const overlayData = dateRange.map((date) => ({
      date,
      [rk]: lookup.get(date) ?? null,
    }));

    const lineColor =
      OVERLAY_COLORS[acc.colorIdx++ % OVERLAY_COLORS.length] ?? "var(--color-chart-1)";
    elements.push(
      <Line
        key={`overlay-ratio-${rk}`}
        data={overlayData}
        dataKey={rk}
        yAxisId="overlay"
        stroke={lineColor}
        strokeWidth={1.5}
        strokeDasharray="4 4"
        dot={false}
        connectNulls
      />,
    );
  }
  return elements;
}

function buildEventOverlays(
  chartType: ChartType,
  strategyEvents: StrategyEvent[],
  strategyEventMeta: StrategyEventMeta[],
  dateRange: string[],
  visibleOverlays: Record<string, boolean>,
): React.ReactElement[] {
  const elements: React.ReactElement[] = [];
  for (const meta of strategyEventMeta) {
    const eventKey = `${chartType}:event:${meta.key}`;
    if (!visibleOverlays[eventKey]) continue;

    const events = strategyEvents.filter(
      (e) => e.event_type === meta.key && dateRange.includes(e.date),
    );

    for (const event of events) {
      if (meta.kind === "point") {
        elements.push(
          <ReferenceLine
            key={`event-point-${meta.key}-${event.date}`}
            x={event.date}
            stroke={meta.color || "var(--color-muted-foreground)"}
            strokeDasharray="3 3"
            strokeOpacity={0.6}
          />,
        );
      } else if (meta.kind === "span" && event.end_date) {
        elements.push(
          <ReferenceArea
            key={`event-span-${meta.key}-${event.date}`}
            x1={event.date}
            x2={event.end_date}
            fill={meta.color || "var(--color-chart-4)"}
            fillOpacity={0.08}
            strokeOpacity={0}
          />,
        );
      }
    }
  }
  return elements;
}

export function useOverlayRenderer({
  chartType,
  indicatorSeries,
  strategyEvents,
  strategyEventMeta,
  dateRange,
}: OverlayRendererProps) {
  const { visibleOverlays } = useOverlayStore();

  const elements = useMemo(() => {
    const acc: OverlayAccumulator = {
      result: [],
      colorIdx: 0,
      needsSecondaryAxis: false,
    };

    for (const series of indicatorSeries) {
      const key = `${chartType}:${series.meta.key}`;
      if (!visibleOverlays[key]) continue;

      const color = OVERLAY_COLORS[acc.colorIdx % OVERLAY_COLORS.length] ?? "var(--color-chart-1)";
      acc.colorIdx++;

      if (series.meta.kind === "continuous") {
        acc.needsSecondaryAxis = true;
        acc.result.push(...buildContinuousOverlay(series, dateRange, color));
      } else if (series.meta.kind === "boolean") {
        acc.result.push(...buildBooleanOverlay(series, dateRange, color));
      } else if (series.meta.kind === "ratio") {
        acc.needsSecondaryAxis = true;
        acc.result.push(...buildRatioOverlay(series, indicatorSeries, dateRange, acc));
      }
    }

    acc.result.push(
      ...buildEventOverlays(
        chartType,
        strategyEvents,
        strategyEventMeta,
        dateRange,
        visibleOverlays,
      ),
    );

    return { elements: acc.result, hasSecondaryAxis: acc.needsSecondaryAxis };
  }, [chartType, indicatorSeries, strategyEvents, strategyEventMeta, dateRange, visibleOverlays]);

  return elements;
}

export function OverlayRenderer(props: OverlayRendererProps) {
  const { elements, hasSecondaryAxis } = useOverlayRenderer(props);

  return (
    <Fragment>
      {hasSecondaryAxis && (
        <YAxis
          yAxisId="overlay"
          orientation="right"
          tick={{ fill: "var(--color-muted-foreground)", fontSize: 10 }}
          width={50}
        />
      )}
      {elements}
    </Fragment>
  );
}
