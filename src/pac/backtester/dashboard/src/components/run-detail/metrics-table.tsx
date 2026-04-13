import { MetricFormatter } from "@/components/metric-formatter";
import { TrendIndicator } from "@/components/trend-indicator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { METRIC_DISPLAY_MAP } from "@/lib/derive";
import { cn } from "@/lib/utils";
import type { MetricValue } from "@/types/api";

export interface MetricsTableProps {
  metrics: Record<string, Record<string, MetricValue>>;
  className?: string;
}

type FormatterFormat = "ratio" | "decimal" | "percent";

function resolveFormat(displayFormat: string): FormatterFormat {
  if (displayFormat === "ratio") return "ratio";
  if (displayFormat === "decimal") return "decimal";
  return "percent";
}

function MetricBand({ metric, format }: { metric: MetricValue; format: FormatterFormat }) {
  return (
    <span className="text-muted-foreground text-xs">
      <MetricFormatter value={metric.p5} format={format} />
      {" – "}
      <MetricFormatter value={metric.p95} format={format} />
    </span>
  );
}

interface MetricRowProps {
  metricKey: string;
  strategyMetric: MetricValue | undefined;
  benchmarkMetric: MetricValue | undefined;
  hasBenchmark: boolean;
}

function MetricRow({ metricKey, strategyMetric, benchmarkMetric, hasBenchmark }: MetricRowProps) {
  const display = METRIC_DISPLAY_MAP[metricKey];
  if (!display) return null;

  const fmt = resolveFormat(display.format);
  const strategyMedian = strategyMetric?.median ?? null;
  const benchmarkMedian = benchmarkMetric?.median ?? null;
  const delta =
    strategyMedian != null && benchmarkMedian != null ? strategyMedian - benchmarkMedian : null;
  const trendFormat: "percent" | "absolute" = display.format === "percent" ? "percent" : "absolute";

  return (
    <TableRow key={metricKey}>
      <TableCell className="font-medium">{display.label}</TableCell>
      <TableCell className="text-right">
        <div className="flex flex-col items-end">
          <MetricFormatter value={strategyMedian} format={fmt} />
          {strategyMetric && <MetricBand metric={strategyMetric} format={fmt} />}
        </div>
      </TableCell>
      {hasBenchmark && (
        <TableCell className="text-right">
          <div className="flex flex-col items-end">
            <MetricFormatter value={benchmarkMedian} format={fmt} />
            {benchmarkMetric && <MetricBand metric={benchmarkMetric} format={fmt} />}
          </div>
        </TableCell>
      )}
      {hasBenchmark && (
        <TableCell className="text-right">
          {delta != null ? (
            <TrendIndicator value={delta} format={trendFormat} invertColor={display.invertColor} />
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </TableCell>
      )}
    </TableRow>
  );
}

export function MetricsTable({ metrics, className }: MetricsTableProps) {
  const strategyMetrics = metrics.strategy ?? {};
  const benchmarkMetrics = metrics.benchmark;
  const hasBenchmark = benchmarkMetrics != null && Object.keys(benchmarkMetrics).length > 0;

  const metricKeys = Object.keys(strategyMetrics).filter((k) => METRIC_DISPLAY_MAP[k] != null);

  if (metricKeys.length === 0) {
    return null;
  }

  return (
    <div className={cn("rounded-lg border", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Metric</TableHead>
            <TableHead className="text-right">Strategy</TableHead>
            {hasBenchmark && <TableHead className="text-right">Benchmark</TableHead>}
            {hasBenchmark && <TableHead className="text-right">Delta</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {metricKeys.map((key) => (
            <MetricRow
              key={key}
              metricKey={key}
              strategyMetric={strategyMetrics[key]}
              benchmarkMetric={hasBenchmark ? benchmarkMetrics[key] : undefined}
              hasBenchmark={hasBenchmark}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
