import type { ColumnDef, VisibilityState } from "@tanstack/react-table";
import { MetricFormatter } from "@/components/metric-formatter";
import { Badge } from "@/components/ui/badge";
import type { TradeWithAttribution } from "@/lib/derive";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const TYPE_STYLES: Record<string, string> = {
  pac_execution: "bg-info/10 text-info border-info/20",
  hard_rebalance: "bg-warning/10 text-warning border-warning/20",
};

const DIRECTION_STYLES: Record<string, string> = {
  buy: "bg-success/10 text-success border-success/20",
  sell: "bg-danger/10 text-danger border-danger/20",
};

export const DEFAULT_TRADES_VISIBILITY: VisibilityState = {
  quantity: false,
  price: false,
};

export function createTradesColumns(): ColumnDef<TradeWithAttribution, unknown>[] {
  return [
    {
      accessorKey: "date",
      header: "Date",
      cell: ({ row }) => formatDate(row.original.date, "short"),
      enableSorting: true,
    },
    {
      accessorKey: "type",
      header: "Type",
      cell: ({ row }) => {
        const type = row.original.type;
        const label = type === "pac_execution" ? "PAC" : "Rebalance";
        return (
          <Badge
            variant="outline"
            className={cn(TYPE_STYLES[type] ?? "bg-muted text-muted-foreground border-border")}
          >
            {label}
          </Badge>
        );
      },
      enableSorting: true,
    },
    {
      accessorKey: "asset_id",
      header: "Asset",
      cell: ({ row }) => <span className="font-medium">{row.original.asset_id}</span>,
      enableSorting: true,
    },
    {
      accessorKey: "direction",
      header: "Direction",
      cell: ({ row }) => {
        const dir = row.original.direction;
        return (
          <Badge
            variant="outline"
            className={cn(DIRECTION_STYLES[dir] ?? "bg-muted text-muted-foreground border-border")}
          >
            {dir}
          </Badge>
        );
      },
      enableSorting: true,
    },
    {
      accessorKey: "amount_eur",
      header: "Amount",
      cell: ({ row }) => <MetricFormatter format="currency" value={row.original.amount_eur} />,
      enableSorting: true,
    },
    {
      accessorKey: "quantity",
      header: "Quantity",
      cell: ({ row }) => (
        <MetricFormatter format="decimal" value={row.original.quantity} decimals={4} />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "price",
      header: "Price",
      cell: ({ row }) => <MetricFormatter format="currency" value={row.original.price} />,
      enableSorting: true,
    },
    {
      accessorKey: "fee",
      header: "Fee",
      cell: ({ row }) => <MetricFormatter format="currency" value={row.original.fee} />,
      enableSorting: true,
    },
    {
      accessorKey: "skipped",
      header: "Status",
      cell: ({ row }) => {
        const skipped = row.original.skipped;
        return (
          <Badge
            variant="outline"
            className={cn(
              skipped
                ? "bg-warning/10 text-warning border-warning/20"
                : "bg-success/10 text-success border-success/20",
            )}
          >
            {skipped ? "Skipped" : "Executed"}
          </Badge>
        );
      },
      enableSorting: true,
    },
    {
      id: "signal_attribution",
      header: "Signal",
      cell: ({ row }) => {
        const signals = row.original.attributedSignals;
        if (row.original.type === "pac_execution") {
          return <span className="text-muted-foreground text-xs">PAC (scheduled)</span>;
        }
        if (signals.length === 0) {
          return <span className="text-muted-foreground text-xs">—</span>;
        }
        const primary = signals[0];
        if (!primary) return <span className="text-muted-foreground text-xs">—</span>;
        return (
          <span className="text-xs">
            {primary.rule_name}
            {signals.length > 1 && (
              <span className="text-muted-foreground ml-1">(+{signals.length - 1})</span>
            )}
          </span>
        );
      },
      enableSorting: false,
    },
  ];
}
