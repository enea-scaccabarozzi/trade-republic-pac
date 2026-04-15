import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { useRunQuantstats } from "@/hooks/use-research";
import { formatDecimal } from "@/lib/format";

interface QuantstatsTabProps {
	runId: string;
	metrics: Record<string, number> | null;
	reportPath: string | null;
}

export function QuantstatsTab({
	runId,
	metrics,
	reportPath,
}: QuantstatsTabProps) {
	const [reportOpen, setReportOpen] = useState(false);

	return (
		<div className="space-y-6">
			{metrics && Object.keys(metrics).length > 0 && (
				<Card>
					<CardHeader>
						<CardTitle className="text-sm">Quantstats Metrics</CardTitle>
					</CardHeader>
					<CardContent>
						<Table>
							<TableHeader>
								<TableRow>
									<TableHead>Metric</TableHead>
									<TableHead className="text-right">Value</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{Object.entries(metrics).map(([key, value]) => (
									<TableRow key={key}>
										<TableCell className="font-medium capitalize">
											{key.replace(/_/g, " ")}
										</TableCell>
										<TableCell className="text-right font-mono">
											{formatDecimal(value, 4)}
										</TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>
					</CardContent>
				</Card>
			)}

			{reportPath && (
				<>
					<Button variant="outline" onClick={() => setReportOpen(true)}>
						View Full Report
					</Button>
					<QuantstatsReportDialog
						runId={runId}
						open={reportOpen}
						onOpenChange={setReportOpen}
					/>
				</>
			)}

			{!metrics && !reportPath && (
				<p className="text-sm text-muted-foreground">
					No quantstats data available.
				</p>
			)}
		</div>
	);
}

function QuantstatsReportDialog({
	runId,
	open,
	onOpenChange,
}: {
	runId: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const { data: html, isPending } = useRunQuantstats(runId, "html");

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-5xl">
				<DialogHeader>
					<DialogTitle>Quantstats Report</DialogTitle>
				</DialogHeader>
				{isPending ? (
					<Skeleton className="h-[80vh] w-full" />
				) : (
					<iframe
						title="Quantstats Report"
						srcDoc={typeof html === "string" ? html : undefined}
						sandbox="allow-same-origin"
						className="h-[80vh] w-full rounded-md border"
					/>
				)}
			</DialogContent>
		</Dialog>
	);
}
