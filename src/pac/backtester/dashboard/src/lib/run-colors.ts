/** Chart palette CSS variable names — matches Tailwind theme tokens. */
export const CHART_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
  "var(--color-chart-7)",
  "var(--color-chart-8)",
] as const;

export interface RunColor {
  runId: string;
  color: string;
  label: string;
}

/**
 * Assign stable colors to runs based on array position.
 * Returns one RunColor per run, capped at CHART_COLORS.length (8).
 */
export function assignRunColors(
  runs: Array<{ run_id: string; config: { strategy: string } }>,
): RunColor[] {
  return runs.slice(0, CHART_COLORS.length).map((run, i) => ({
    runId: run.run_id,
    color: CHART_COLORS[i % CHART_COLORS.length] ?? "var(--color-muted-foreground)",
    label: `${run.config.strategy} (${run.run_id.slice(0, 8)})`,
  }));
}
