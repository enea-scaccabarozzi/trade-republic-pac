import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { StrategyEvent, StrategyEventMeta } from "@/types/api";

interface StrategyEventTimelineProps {
  events: StrategyEvent[];
  eventMeta: StrategyEventMeta[];
  startDate: string;
  endDate: string;
  className?: string;
}

const COLOR_MAP: Record<string, string> = {
  blue: "var(--color-info)",
  red: "var(--color-danger)",
  gray: "var(--color-muted-foreground)",
  green: "var(--color-success)",
  amber: "var(--color-warning)",
};

function resolveColor(color: string): string {
  return COLOR_MAP[color] ?? color ?? "var(--color-chart-1)";
}

interface TooltipState {
  x: number;
  y: number;
  event: StrategyEvent;
  meta: StrategyEventMeta;
}

const LANE_HEIGHT = 32;
const LABEL_WIDTH = 140;
const AXIS_HEIGHT = 24;

export function StrategyEventTimeline({
  events,
  eventMeta,
  startDate,
  endDate,
  className,
}: StrategyEventTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rafId = useRef(0);
  const [svgWidth, setSvgWidth] = useState(800);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(rafId.current);
      rafId.current = requestAnimationFrame(() => {
        setSvgWidth(el.clientWidth);
      });
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(rafId.current);
    };
  }, []);

  if (events.length === 0) {
    return (
      <p className={cn("text-muted-foreground py-8 text-center text-sm", className)}>
        No strategy events recorded
      </p>
    );
  }

  const startMs = new Date(startDate).getTime();
  const endMs = new Date(endDate).getTime();
  const rangeMs = endMs - startMs;
  const chartWidth = svgWidth - LABEL_WIDTH;

  const dateToX = (dateStr: string) =>
    LABEL_WIDTH + ((new Date(dateStr).getTime() - startMs) / rangeMs) * chartWidth;

  // Build lanes from eventMeta
  const metaByKey = new Map(eventMeta.map((m) => [m.key, m]));
  const lanes = eventMeta.map((meta) => {
    const laneEvents = events.filter((e) => e.event_type === meta.key);
    return {
      key: meta.key,
      displayName: meta.display_name,
      color: resolveColor(meta.color),
      spans: laneEvents.filter(
        (e) => metaByKey.get(e.event_type)?.kind === "span" && e.end_date !== null,
      ),
      points: laneEvents.filter(
        (e) => metaByKey.get(e.event_type)?.kind === "point" || e.end_date === null,
      ),
    };
  });

  const totalHeight = lanes.length * LANE_HEIGHT + AXIS_HEIGHT;

  // Year ticks
  const startYear = new Date(startDate).getFullYear();
  const endYear = new Date(endDate).getFullYear();
  const yearTicks: string[] = [];
  for (let y = startYear + 1; y <= endYear; y++) {
    yearTicks.push(`${y}-01-01`);
  }

  // Skip every other year on narrow containers
  const skipYears = svgWidth < 500;
  const visibleTicks = skipYears ? yearTicks.filter((_, i) => i % 2 === 0) : yearTicks;

  const showTooltip = (e: React.MouseEvent, event: StrategyEvent, meta: StrategyEventMeta) => {
    setTooltip({ x: e.clientX, y: e.clientY, event, meta });
  };

  const hideTooltip = () => setTooltip(null);

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <svg width="100%" viewBox={`0 0 ${svgWidth} ${totalHeight}`} className="overflow-visible">
        <title>Strategy Event Timeline</title>
        {/* Grid lines */}
        {visibleTicks.map((tick) => (
          <line
            key={tick}
            x1={dateToX(tick)}
            y1={0}
            x2={dateToX(tick)}
            y2={lanes.length * LANE_HEIGHT}
            stroke="var(--color-border)"
            strokeDasharray="2 4"
          />
        ))}

        {/* Swim lane labels */}
        {lanes.map((lane, i) => (
          <text
            key={`label-${lane.key}`}
            x={8}
            y={i * LANE_HEIGHT + LANE_HEIGHT / 2}
            dominantBaseline="central"
            className="fill-muted-foreground text-xs"
          >
            {lane.displayName}
          </text>
        ))}

        {/* Swim lanes */}
        {lanes.map((lane, i) => (
          <g key={lane.key}>
            {/* Spans */}
            {lane.spans.map((span, j) => {
              return (
                // biome-ignore lint/a11y/useSemanticElements: SVG rect cannot be replaced with a semantic HTML element
                <rect
                  key={`span-${span.event_type}-${span.date}`}
                  role="button"
                  tabIndex={j}
                  x={dateToX(span.date)}
                  y={i * LANE_HEIGHT + LANE_HEIGHT * 0.2}
                  width={Math.max(2, dateToX(span.end_date ?? span.date) - dateToX(span.date))}
                  height={LANE_HEIGHT * 0.6}
                  rx={3}
                  fill={lane.color}
                  fillOpacity={0.3}
                  stroke={lane.color}
                  strokeWidth={1}
                  className="cursor-pointer"
                  onMouseEnter={(e) => {
                    const meta = metaByKey.get(span.event_type);
                    if (meta) showTooltip(e, span, meta);
                  }}
                  onMouseLeave={hideTooltip}
                />
              );
            })}
            {/* Points */}
            {lane.points.map((point, j) => {
              return (
                // biome-ignore lint/a11y/useSemanticElements: SVG circle cannot be replaced with a semantic HTML element
                <circle
                  key={`point-${point.event_type}-${point.date}`}
                  role="button"
                  tabIndex={j}
                  cx={dateToX(point.date)}
                  cy={i * LANE_HEIGHT + LANE_HEIGHT / 2}
                  r={5}
                  fill={lane.color}
                  className="cursor-pointer"
                  onMouseEnter={(e) => {
                    const meta = metaByKey.get(point.event_type);
                    if (meta) showTooltip(e, point, meta);
                  }}
                  onMouseLeave={hideTooltip}
                />
              );
            })}
          </g>
        ))}

        {/* X-axis ticks */}
        {visibleTicks.map((tick) => (
          <text
            key={`axis-${tick}`}
            x={dateToX(tick)}
            y={lanes.length * LANE_HEIGHT + 16}
            textAnchor="middle"
            className="fill-muted-foreground text-xs"
          >
            {new Date(tick).getFullYear()}
          </text>
        ))}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none fixed z-50 max-w-xs rounded-md border bg-popover px-3 py-2 text-popover-foreground shadow-md"
          style={{
            left: tooltip.x + 12,
            top: tooltip.y - 10,
          }}
        >
          <p className="text-xs font-medium">{tooltip.meta.display_name}</p>
          <p className="text-muted-foreground text-xs">
            {tooltip.event.date}
            {tooltip.event.end_date && ` – ${tooltip.event.end_date}`}
          </p>
          {Object.keys(tooltip.event.details).length > 0 && (
            <pre className="text-muted-foreground mt-1 text-xs">
              {JSON.stringify(tooltip.event.details, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
