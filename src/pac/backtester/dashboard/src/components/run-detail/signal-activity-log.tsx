import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { DataTable } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { SearchToolbar } from "@/components/search-toolbar";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SignalRecord } from "@/types/api";

interface SignalActivityLogProps {
  signalLog: SignalRecord[];
  className?: string;
}

const SEVERITY_VARIANT: Record<string, string> = {
  critical: "bg-danger/10 text-danger border-danger/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  info: "bg-info/10 text-info border-info/20",
};

const columns: ColumnDef<SignalRecord, unknown>[] = [
  {
    accessorKey: "date",
    header: "Date",
    cell: ({ row }) => formatDate(row.original.date, "short"),
    enableSorting: true,
  },
  {
    accessorKey: "rule_name",
    header: "Rule",
    cell: ({ row }) => <span className="font-medium">{row.original.rule_name}</span>,
    enableSorting: true,
  },
  {
    accessorKey: "severity",
    header: "Severity",
    cell: ({ row }) => {
      const severity = row.original.severity;
      return (
        <Badge
          variant="outline"
          className={cn(
            SEVERITY_VARIANT[severity] ?? "bg-muted text-muted-foreground border-border",
          )}
        >
          {severity}
        </Badge>
      );
    },
    enableSorting: true,
  },
  {
    accessorKey: "message",
    header: "Details",
    cell: ({ row }) => {
      const msg = row.original.message;
      if (msg.length <= 80) {
        return <span className="text-sm">{msg}</span>;
      }
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-sm cursor-default">{msg.slice(0, 80)}…</span>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm">{msg}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    },
    enableSorting: false,
  },
  {
    accessorKey: "metadata",
    header: "Metadata",
    cell: ({ row }) => {
      const meta = row.original.metadata;
      if (!meta || Object.keys(meta).length === 0) {
        return <span className="text-muted-foreground">—</span>;
      }
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-muted-foreground cursor-default text-xs">
                {Object.keys(meta).length} fields
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm">
              <pre className="text-xs">{JSON.stringify(meta, null, 2)}</pre>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    },
    enableSorting: false,
  },
];

export function SignalActivityLog({ signalLog, className }: SignalActivityLogProps) {
  const [search, setSearch] = useState("");
  const [ruleFilter, setRuleFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  const uniqueRules = useMemo(
    () => [...new Set(signalLog.map((s) => s.rule_name))].sort(),
    [signalLog],
  );

  const uniqueSeverities = useMemo(
    () => [...new Set(signalLog.map((s) => s.severity))].sort(),
    [signalLog],
  );

  const filteredSignals = useMemo(() => {
    const matchesRule = (s: SignalRecord) => ruleFilter === "all" || s.rule_name === ruleFilter;
    const matchesSeverity = (s: SignalRecord) =>
      severityFilter === "all" || s.severity === severityFilter;
    const matchesSearch = (s: SignalRecord) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return s.message.toLowerCase().includes(q) || s.rule_name.toLowerCase().includes(q);
    };
    return signalLog.filter((s) => matchesRule(s) && matchesSeverity(s) && matchesSearch(s));
  }, [signalLog, ruleFilter, severityFilter, search]);

  if (signalLog.length === 0) {
    return (
      <EmptyState
        title="No signals recorded"
        description="This backtest run did not produce any signal triggers."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <SearchToolbar value={search} onChange={setSearch} placeholder="Search signals...">
        <Select value={ruleFilter} onValueChange={setRuleFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All rules" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All rules</SelectItem>
            {uniqueRules.map((rule) => (
              <SelectItem key={rule} value={rule}>
                {rule}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={severityFilter} onValueChange={setSeverityFilter}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All severities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All severities</SelectItem>
            {uniqueSeverities.map((sev) => (
              <SelectItem key={sev} value={sev}>
                {sev}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </SearchToolbar>
      <p className="text-muted-foreground text-sm">
        {filteredSignals.length === signalLog.length
          ? `${filteredSignals.length} signals`
          : `${filteredSignals.length} of ${signalLog.length} signals`}
      </p>
      <DataTable
        columns={columns}
        data={filteredSignals}
        sorting
        initialSorting={[{ id: "date", desc: true }]}
        pageSize={20}
      />
    </div>
  );
}
