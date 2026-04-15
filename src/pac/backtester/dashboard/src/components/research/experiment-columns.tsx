import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { StatusBadge } from "@/components/research/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import type { ExperimentSummary } from "@/types/api";

function SortableHeader({
	column,
	children,
}: {
	column: {
		getIsSorted: () => false | "asc" | "desc";
		toggleSorting: (desc?: boolean) => void;
	};
	children: React.ReactNode;
}) {
	const sorted = column.getIsSorted();
	return (
		<Button
			variant="ghost"
			size="sm"
			className="-ml-3"
			onClick={() => column.toggleSorting()}
		>
			{children}
			{sorted === "asc" && <ArrowUp className="ml-1 size-3.5" />}
			{sorted === "desc" && <ArrowDown className="ml-1 size-3.5" />}
			{!sorted && <ArrowUpDown className="ml-1 size-3.5" />}
		</Button>
	);
}

export function createExperimentColumns(): ColumnDef<
	ExperimentSummary,
	unknown
>[] {
	return [
		{
			accessorKey: "slug",
			header: ({ column }) => (
				<SortableHeader column={column}>ID</SortableHeader>
			),
			cell: ({ row }) => (
				<span className="font-mono text-xs">{row.getValue("slug")}</span>
			),
		},
		{
			accessorKey: "title",
			header: ({ column }) => (
				<SortableHeader column={column}>Title</SortableHeader>
			),
			cell: ({ row }) => (
				<Link
					to="/research/$id"
					params={{ id: row.original.id }}
					className="font-medium hover:underline"
					onClick={(e) => e.stopPropagation()}
				>
					{row.getValue("title")}
				</Link>
			),
		},
		{
			accessorKey: "status",
			header: ({ column }) => (
				<SortableHeader column={column}>Status</SortableHeader>
			),
			cell: ({ row }) => <StatusBadge status={row.getValue("status")} />,
		},
		{
			accessorKey: "strategy_name",
			header: ({ column }) => (
				<SortableHeader column={column}>Strategy</SortableHeader>
			),
			cell: ({ row }) => (
				<span className="text-muted-foreground text-sm">
					{row.getValue("strategy_name") ?? "—"}
				</span>
			),
		},
		{
			accessorKey: "tags",
			header: "Tags",
			cell: ({ row }) => {
				const tags = row.getValue("tags") as string[];
				return (
					<div className="flex flex-wrap gap-1">
						{tags.map((tag) => (
							<Badge key={tag} variant="secondary" className="text-xs">
								{tag}
							</Badge>
						))}
					</div>
				);
			},
			enableSorting: false,
		},
		{
			accessorKey: "created",
			header: ({ column }) => (
				<SortableHeader column={column}>Created</SortableHeader>
			),
			cell: ({ row }) => (
				<span className="text-muted-foreground text-sm">
					{formatDate(row.getValue("created"))}
				</span>
			),
		},
		{
			accessorKey: "artifact_count",
			header: ({ column }) => (
				<SortableHeader column={column}>Artifacts</SortableHeader>
			),
			cell: ({ row }) => (
				<span className="text-right">{row.getValue("artifact_count")}</span>
			),
		},
		{
			accessorKey: "report_count",
			header: ({ column }) => (
				<SortableHeader column={column}>Reports</SortableHeader>
			),
			cell: ({ row }) => (
				<span className="text-right">{row.getValue("report_count")}</span>
			),
		},
		{
			accessorKey: "result_file_count",
			header: ({ column }) => (
				<SortableHeader column={column}>Results</SortableHeader>
			),
			cell: ({ row }) => (
				<span className="text-right">{row.getValue("result_file_count")}</span>
			),
		},
	];
}
