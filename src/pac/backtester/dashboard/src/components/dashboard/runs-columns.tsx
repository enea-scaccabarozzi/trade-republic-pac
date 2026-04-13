import type { ColumnDef } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Copy, Eye, MoreHorizontal, Trash2 } from "lucide-react";
import { MetricFormatter } from "@/components/metric-formatter";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatDate } from "@/lib/format";
import type { RunSummary } from "@/types/api";

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
    <Button variant="ghost" size="sm" className="-ml-3" onClick={() => column.toggleSorting()}>
      {children}
      {sorted === "asc" && <ArrowUp className="ml-1 size-3.5" />}
      {sorted === "desc" && <ArrowDown className="ml-1 size-3.5" />}
      {!sorted && <ArrowUpDown className="ml-1 size-3.5" />}
    </Button>
  );
}

export function createRunsColumns(opts: {
  onView: (runId: string) => void;
  onClone: (runId: string) => void;
  onDelete: (runId: string) => void;
}): ColumnDef<RunSummary, unknown>[] {
  return [
    {
      accessorKey: "strategy",
      header: ({ column }) => <SortableHeader column={column}>Strategy</SortableHeader>,
      cell: ({ row }) => <span className="font-medium">{row.getValue("strategy")}</span>,
    },
    {
      id: "dateRange",
      accessorFn: (row) => row.start_date,
      header: ({ column }) => <SortableHeader column={column}>Date Range</SortableHeader>,
      cell: ({ row }) =>
        `${formatDate(row.original.start_date, "short")} – ${formatDate(row.original.end_date, "short")}`,
    },
    {
      accessorKey: "final_value_median",
      header: ({ column }) => <SortableHeader column={column}>Final Value</SortableHeader>,
      cell: ({ row }) => (
        <MetricFormatter value={row.original.final_value_median} format="currency" />
      ),
    },
    {
      accessorKey: "cagr_median",
      header: ({ column }) => <SortableHeader column={column}>CAGR</SortableHeader>,
      cell: ({ row }) => (
        <MetricFormatter value={row.original.cagr_median} format="percent" colorize />
      ),
    },
    {
      accessorKey: "sharpe_median",
      header: ({ column }) => <SortableHeader column={column}>Sharpe</SortableHeader>,
      cell: ({ row }) => <MetricFormatter value={row.original.sharpe_median} format="ratio" />,
    },
    {
      accessorKey: "max_drawdown_median",
      header: ({ column }) => <SortableHeader column={column}>Max Drawdown</SortableHeader>,
      cell: ({ row }) => (
        <MetricFormatter value={row.original.max_drawdown_median} format="percent" colorize />
      ),
    },
    {
      accessorKey: "iterations",
      header: ({ column }) => <SortableHeader column={column}>Iters</SortableHeader>,
      cell: ({ row }) => <MetricFormatter value={row.original.iterations} format="integer" />,
    },
    {
      accessorKey: "created_at",
      header: ({ column }) => <SortableHeader column={column}>Created</SortableHeader>,
      cell: ({ row }) => formatDate(row.original.created_at, "short"),
    },
    {
      id: "actions",
      meta: { noRowClick: true },
      cell: ({ row }) => {
        const runId = row.original.run_id;
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="size-8">
                <MoreHorizontal className="size-4" />
                <span className="sr-only">Actions</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => opts.onView(runId)}>
                <Eye className="mr-2 size-4" />
                View
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => opts.onClone(runId)}>
                <Copy className="mr-2 size-4" />
                Clone & Tweak
              </DropdownMenuItem>
              <DropdownMenuItem className="text-destructive" onClick={() => opts.onDelete(runId)}>
                <Trash2 className="mr-2 size-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];
}
