import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChartContainer } from "@/components/chart-container";
import { EmptyState } from "@/components/empty-state";
import { computeSignalDensity } from "@/lib/derive";
import type { RunColor } from "@/lib/run-colors";
import { cn } from "@/lib/utils";
import type { RunResult } from "@/types/api";

export interface SignalActivityHeatmapProps {
  runs: RunResult[];
  runColors: RunColor[];
  className?: string;
}

const LABEL_WIDTH = 180;
const ROW_HEIGHT = 24;
const CELL_GAP = 1;

export function SignalActivityHeatmap({ runs, runColors, className }: SignalActivityHeatmapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    label: string;
    month: string;
    count: number;
  } | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setContainerWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { densities, allMonths, globalMax } = useMemo(
    () =>
      computeSignalDensity(
        runs.map((r, i) => ({
          runId: r.run_id,
          label: runColors[i]?.label ?? r.run_id.slice(0, 8),
          signalLog: r.signal_log,
        })),
      ),
    [runs, runColors],
  );

  const densityMaps = useMemo(() => {
    return densities.map((d) => {
      const map = new Map<string, number>();
      for (const pt of d.density) {
        map.set(pt.month, pt.count);
      }
      return { runId: d.runId, label: d.label, map };
    });
  }, [densities]);

  const cellWidth = Math.max(
    3,
    (containerWidth - LABEL_WIDTH) / Math.max(allMonths.length, 1) - CELL_GAP,
  );
  const svgWidth = LABEL_WIDTH + allMonths.length * (cellWidth + CELL_GAP);
  const svgHeight = densities.length * ROW_HEIGHT + 20;

  const yearTicks = useMemo(() => {
    const ticks: Array<{ month: string; label: string; x: number }> = [];
    const yearsAdded = new Set<string>();
    const step = allMonths.length > 120 ? 2 : 1;
    for (let i = 0; i < allMonths.length; i++) {
      const m = allMonths[i];
      if (!m?.endsWith("-01")) continue;
      const year = m.slice(0, 4);
      if (yearsAdded.has(year)) continue;
      const yearNum = Number(year);
      if (step === 2 && yearNum % 2 !== 0) continue;
      yearsAdded.add(year);
      ticks.push({
        month: m,
        label: `'${year.slice(2)}`,
        x: LABEL_WIDTH + i * (cellWidth + CELL_GAP) + cellWidth / 2,
      });
    }
    return ticks;
  }, [allMonths, cellWidth]);

  const handleMouseEnter = useCallback(
    (e: React.MouseEvent<SVGRectElement>, label: string, month: string, count: number) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const container = containerRef.current?.getBoundingClientRect();
      if (!container) return;
      setTooltip({
        x: rect.left - container.left + rect.width / 2,
        y: rect.top - container.top - 8,
        label,
        month,
        count,
      });
    },
    [],
  );

  const hasSignals = densities.some((d) => d.density.length > 0);

  if (!hasSignals) {
    return (
      <ChartContainer title="Signal Activity" className={cn(className)}>
        <EmptyState
          title="No signal activity"
          description="None of the selected runs produced signal triggers."
        />
      </ChartContainer>
    );
  }

  return (
    <ChartContainer
      title="Signal Activity"
      description="Monthly signal density per run"
      className={cn(className)}
    >
      <div ref={containerRef} className="relative overflow-x-auto">
        <svg
          width={Math.max(svgWidth, containerWidth)}
          height={svgHeight}
          className="block"
          role="img"
          aria-label="Signal activity heatmap showing monthly signal density per run"
        >
          {/* Y-axis labels */}
          {densityMaps.map((d, rowIdx) => (
            <g key={d.runId}>
              <circle
                cx={12}
                cy={rowIdx * ROW_HEIGHT + ROW_HEIGHT / 2}
                r={4}
                fill={runColors[rowIdx]?.color ?? "var(--color-muted-foreground)"}
              />
              <text
                x={22}
                y={rowIdx * ROW_HEIGHT + ROW_HEIGHT / 2}
                dominantBaseline="central"
                className="fill-muted-foreground text-[11px]"
              >
                {d.label.length > 24 ? `${d.label.slice(0, 22)}…` : d.label}
              </text>
            </g>
          ))}

          {/* Heatmap cells */}
          {densityMaps.map((d, rowIdx) =>
            allMonths.map((month, colIdx) => {
              const count = d.map.get(month) ?? 0;
              const opacity = count === 0 ? 0 : Math.max(0.15, count / globalMax);
              return (
                // biome-ignore lint/a11y/noStaticElementInteractions: SVG tooltip hover
                <rect
                  key={`${d.runId}-${month}`}
                  x={LABEL_WIDTH + colIdx * (cellWidth + CELL_GAP)}
                  y={rowIdx * ROW_HEIGHT + 2}
                  width={cellWidth}
                  height={ROW_HEIGHT - 4}
                  rx={2}
                  fill={runColors[rowIdx]?.color ?? "var(--color-muted-foreground)"}
                  fillOpacity={opacity}
                  className="cursor-default"
                  onMouseEnter={(e) => handleMouseEnter(e, d.label, month, count)}
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            }),
          )}

          {/* X-axis year ticks */}
          {yearTicks.map((t) => (
            <text
              key={t.month}
              x={t.x}
              y={svgHeight - 4}
              textAnchor="middle"
              className="fill-muted-foreground text-[10px]"
            >
              {t.label}
            </text>
          ))}
        </svg>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border bg-popover px-2 py-1 text-xs shadow-md"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            <p className="font-medium">{tooltip.label}</p>
            <p className="text-muted-foreground">
              {tooltip.month} · {tooltip.count} signal
              {tooltip.count !== 1 ? "s" : ""}
            </p>
          </div>
        )}
      </div>
    </ChartContainer>
  );
}
