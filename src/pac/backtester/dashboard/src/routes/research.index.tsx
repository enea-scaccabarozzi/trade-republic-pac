import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
import { useMemo, useState } from "react";
import { DataTable } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { createExperimentColumns } from "@/components/research/experiment-columns";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useExperiments } from "@/hooks/use-research";

export const Route = createFileRoute("/research/")({
	component: ResearchIndex,
});

function ResearchSkeleton() {
	return (
		<div className="space-y-6">
			<div className="space-y-2">
				<Skeleton className="h-8 w-48" />
				<Skeleton className="h-4 w-64" />
			</div>
			<div className="flex gap-3">
				<Skeleton className="h-9 w-40" />
				<Skeleton className="h-9 w-40" />
			</div>
			<Skeleton className="h-10 w-full" />
			{Array.from({ length: 5 }, (_, i) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: static skeleton
				<Skeleton key={i} className="h-8 w-full" />
			))}
		</div>
	);
}

export function ResearchIndex() {
	const navigate = useNavigate();
	const [statusFilter, setStatusFilter] = useState<string>("");
	const [tagFilter, setTagFilter] = useState("");

	const { data, isPending, isError } = useExperiments({
		status: statusFilter || undefined,
		tag: tagFilter || undefined,
	});

	const columns = useMemo(() => createExperimentColumns(), []);

	if (isPending) {
		return <ResearchSkeleton />;
	}

	if (isError) {
		return (
			<EmptyState
				title="Failed to load experiments"
				description="Could not fetch the research experiments."
				action={{
					label: "Back to Dashboard",
					onClick: () => navigate({ to: "/" }),
				}}
			/>
		);
	}

	const experiments = data?.experiments ?? [];

	return (
		<div className="space-y-6">
			<PageHeader
				title="Research"
				description="Browse experiments, papers, and strategy snapshots"
			/>

			<div className="flex flex-wrap gap-3">
				<Select value={statusFilter} onValueChange={setStatusFilter}>
					<SelectTrigger className="w-40">
						<SelectValue placeholder="All statuses" />
					</SelectTrigger>
					<SelectContent>
						<SelectItem value="all">All statuses</SelectItem>
						<SelectItem value="exploring">Exploring</SelectItem>
						<SelectItem value="validated">Validated</SelectItem>
						<SelectItem value="rejected">Rejected</SelectItem>
						<SelectItem value="published">Published</SelectItem>
					</SelectContent>
				</Select>

				<Input
					placeholder="Filter by tag…"
					value={tagFilter}
					onChange={(e) => setTagFilter(e.target.value)}
					className="w-40"
				/>
			</div>

			{experiments.length === 0 ? (
				<EmptyState
					icon={FlaskConical}
					title="No experiments found"
					description="Create an experiment with `just new-experiment <name>`"
				/>
			) : (
				<DataTable
					columns={columns}
					data={experiments}
					sorting
					initialSorting={[{ id: "created", desc: true }]}
					onRowClick={(row) =>
						navigate({ to: "/research/$id", params: { id: row.id } })
					}
					pageSize={20}
					emptyState={<EmptyState title="No experiments found" />}
				/>
			)}
		</div>
	);
}
