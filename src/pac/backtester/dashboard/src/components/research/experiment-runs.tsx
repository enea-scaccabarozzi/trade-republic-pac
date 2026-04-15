import { Link } from "@tanstack/react-router";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunDetail } from "@/hooks/use-run-detail";
import {
	formatCurrency,
	formatDate,
	formatPercent,
	formatRatio,
} from "@/lib/format";

function RunCard({ runId }: { runId: string }) {
	const { data, isPending, isError } = useRunDetail(runId);

	if (isPending) {
		return <Skeleton className="h-28 w-full rounded-xl" />;
	}

	if (isError || !data) {
		return (
			<Card className="border-destructive/20">
				<CardContent className="pt-4">
					<p className="text-sm text-muted-foreground">
						Failed to load run {runId}
					</p>
				</CardContent>
			</Card>
		);
	}

	const run = data.run;
	const strategyMetrics = run.metrics?.strategy ?? {};
	const cagr = strategyMetrics.cagr?.median;
	const sharpe = strategyMetrics.sharpe?.median;
	const maxDD = strategyMetrics.max_drawdown?.median;

	return (
		<Link to="/runs/$id" params={{ id: runId }}>
			<Card className="transition-colors hover:bg-muted/50">
				<CardContent className="pt-4">
					<div className="flex items-start justify-between">
						<div>
							<p className="text-sm font-medium">{run.config.strategy}</p>
							<p className="text-xs text-muted-foreground">
								{formatDate(run.config.start_date)} –{" "}
								{formatDate(run.config.end_date)}
							</p>
						</div>
						<span className="text-xs font-mono text-muted-foreground">
							{runId.slice(0, 8)}
						</span>
					</div>
					<div className="mt-3 flex gap-4 text-xs">
						<div>
							<span className="text-muted-foreground">CAGR</span>{" "}
							<span className="font-medium">
								{cagr != null ? formatPercent(cagr) : "—"}
							</span>
						</div>
						<div>
							<span className="text-muted-foreground">Sharpe</span>{" "}
							<span className="font-medium">
								{sharpe != null ? formatRatio(sharpe) : "—"}
							</span>
						</div>
						<div>
							<span className="text-muted-foreground">MaxDD</span>{" "}
							<span className="font-medium">
								{maxDD != null ? formatPercent(maxDD) : "—"}
							</span>
						</div>
						<div>
							<span className="text-muted-foreground">Value</span>{" "}
							<span className="font-medium">
								{formatCurrency(run.summary.final_value.median)}
							</span>
						</div>
					</div>
				</CardContent>
			</Card>
		</Link>
	);
}

interface ExperimentRunsProps {
	runIds: string[];
}

export function ExperimentRuns({ runIds }: ExperimentRunsProps) {
	return (
		<div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{runIds.map((runId) => (
				<RunCard key={runId} runId={runId} />
			))}
		</div>
	);
}
