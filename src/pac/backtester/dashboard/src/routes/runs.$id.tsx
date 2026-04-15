import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Copy } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ChartsTab } from "@/components/run-detail/charts-tab";
import { OOSTab } from "@/components/run-detail/oos-tab";
import { OverviewTab } from "@/components/run-detail/overview-tab";
import { QuantstatsTab } from "@/components/run-detail/quantstats-tab";
import { SignalsTab } from "@/components/run-detail/signals-tab";
import { TradesTab } from "@/components/run-detail/trades-tab";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useRunDetail } from "@/hooks/use-run-detail";
import { formatDate } from "@/lib/format";

export const Route = createFileRoute("/runs/$id")({
	component: RunDetail,
});

function RunDetailSkeleton() {
	return (
		<div className="space-y-6">
			<div className="space-y-2">
				<Skeleton className="h-8 w-64" />
				<Skeleton className="h-4 w-96" />
			</div>
			<Skeleton className="h-10 w-80" />
			<div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
				{Array.from({ length: 6 }, (_, i) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: static skeleton
					<Skeleton key={i} className="h-[100px] rounded-xl" />
				))}
			</div>
			<Skeleton className="h-12 w-full" />
			<Skeleton className="h-48 w-full" />
		</div>
	);
}

function RunDetail() {
	const { id } = Route.useParams();
	const navigate = useNavigate();
	const { data, isPending, isError } = useRunDetail(id);

	if (isPending) {
		return <RunDetailSkeleton />;
	}

	if (isError || !data) {
		return (
			<EmptyState
				title="Run not found"
				description="This backtest result may have been deleted."
				action={{
					label: "Back to Dashboard",
					onClick: () => navigate({ to: "/" }),
				}}
			/>
		);
	}

	const run = data.run;
	const description = `${formatDate(run.config.start_date)} – ${formatDate(run.config.end_date)} · ${run.monte_carlo.iterations} iterations`;

	return (
		<div className="space-y-6">
			<PageHeader
				title={run.config.strategy}
				description={description}
				actions={
					<Button
						variant="outline"
						size="sm"
						className="gap-1.5"
						onClick={() => navigate({ to: "/run", search: { clone: id } })}
					>
						<Copy className="size-3.5" />
						Clone &amp; Tweak
					</Button>
				}
			/>

			<Tabs defaultValue="overview">
				<TabsList>
					<TabsTrigger value="overview">Overview</TabsTrigger>
					<TabsTrigger value="charts">Charts</TabsTrigger>
					<TabsTrigger value="signals">Signals &amp; Strategy</TabsTrigger>
					<TabsTrigger value="trades">Trades</TabsTrigger>
					{(run.quantstats_metrics || run.quantstats_report_path) && (
						<TabsTrigger value="quantstats">Quantstats</TabsTrigger>
					)}
					{run.oos_metadata && <TabsTrigger value="oos">OOS</TabsTrigger>}
				</TabsList>
				<TabsContent value="overview" className="mt-6">
					<OverviewTab run={run} />
				</TabsContent>
				<TabsContent value="charts" className="mt-6">
					<ChartsTab run={run} />
				</TabsContent>
				<TabsContent value="signals" className="mt-6">
					<SignalsTab run={run} />
				</TabsContent>
				<TabsContent value="trades" className="mt-6">
					<TradesTab run={run} />
				</TabsContent>
				{(run.quantstats_metrics || run.quantstats_report_path) && (
					<TabsContent value="quantstats" className="mt-6">
						<QuantstatsTab
							runId={run.run_id}
							metrics={run.quantstats_metrics}
							reportPath={run.quantstats_report_path}
						/>
					</TabsContent>
				)}
				{run.oos_metadata && (
					<TabsContent value="oos" className="mt-6">
						<OOSTab metadata={run.oos_metadata} />
					</TabsContent>
				)}
			</Tabs>
		</div>
	);
}
