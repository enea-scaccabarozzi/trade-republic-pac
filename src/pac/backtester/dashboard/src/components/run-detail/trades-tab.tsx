import type { VisibilityState } from "@tanstack/react-table";
import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import { TradeFrequencyChart } from "@/components/charts/trade-frequency-chart";
import { ColumnVisibilityToggle } from "@/components/column-visibility-toggle";
import { type DateRange, DateRangeFilter } from "@/components/date-range-filter";
import { EmptyState } from "@/components/empty-state";
import {
  createTradesColumns,
  DEFAULT_TRADES_VISIBILITY,
} from "@/components/run-detail/trades-columns";
import { SearchToolbar } from "@/components/search-toolbar";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { VirtualDataTable } from "@/components/virtual-data-table";
import { exportToCsv } from "@/lib/csv-export";
import { computeSignalAttribution, type TradeWithAttribution } from "@/lib/derive";
import type { RunResult } from "@/types/api";

interface TradesTabProps {
  run: RunResult;
}

export function TradesTab({ run }: TradesTabProps) {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [assetFilter, setAssetFilter] = useState<string>("all");
  const [directionFilter, setDirectionFilter] = useState<string>("all");
  const [dateRange, setDateRange] = useState<DateRange>({
    from: null,
    to: null,
  });
  const [columnVisibility, setColumnVisibility] =
    useState<VisibilityState>(DEFAULT_TRADES_VISIBILITY);

  const columns = useMemo(() => createTradesColumns(), []);

  const tradesWithAttribution = useMemo(
    () => computeSignalAttribution(run.trades, run.signal_log),
    [run.trades, run.signal_log],
  );

  const uniqueAssets = useMemo(
    () => [...new Set(run.trades.map((t) => t.asset_id))].sort(),
    [run.trades],
  );

  const filteredTrades = useMemo(() => {
    const matchesType = (t: TradeWithAttribution) => typeFilter === "all" || t.type === typeFilter;
    const matchesAsset = (t: TradeWithAttribution) =>
      assetFilter === "all" || t.asset_id === assetFilter;
    const matchesDirection = (t: TradeWithAttribution) =>
      directionFilter === "all" || t.direction === directionFilter;
    const matchesDateRange = (t: TradeWithAttribution) => {
      if (dateRange.from && t.date < dateRange.from) return false;
      if (dateRange.to && t.date > dateRange.to) return false;
      return true;
    };
    const matchesSearch = (t: TradeWithAttribution) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        t.asset_id.toLowerCase().includes(q) ||
        t.type.toLowerCase().includes(q) ||
        t.direction.toLowerCase().includes(q)
      );
    };
    return tradesWithAttribution.filter(
      (t) =>
        matchesType(t) &&
        matchesAsset(t) &&
        matchesDirection(t) &&
        matchesDateRange(t) &&
        matchesSearch(t),
    );
  }, [tradesWithAttribution, typeFilter, assetFilter, directionFilter, dateRange, search]);

  const getRowClassName = (trade: TradeWithAttribution): string => {
    if (trade.skipped) return "bg-warning/5 hover:bg-warning/10";
    if (trade.direction === "buy") return "bg-success/5 hover:bg-success/10";
    if (trade.direction === "sell") return "bg-danger/5 hover:bg-danger/10";
    return "";
  };

  function handleExportCsv() {
    exportToCsv(`trades-${run.run_id}.csv`, filteredTrades, [
      { key: "date", header: "Date" },
      { key: "type", header: "Type" },
      { key: "asset_id", header: "Asset" },
      { key: "direction", header: "Direction" },
      { key: "amount_eur", header: "Amount (EUR)" },
      { key: "quantity", header: "Quantity" },
      { key: "price", header: "Price" },
      { key: "fee", header: "Fee" },
      { key: "skipped", header: "Skipped" },
    ]);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <SearchToolbar value={search} onChange={setSearch} placeholder="Search trades...">
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              <SelectItem value="pac_execution">PAC Execution</SelectItem>
              <SelectItem value="hard_rebalance">Hard Rebalance</SelectItem>
            </SelectContent>
          </Select>
          <Select value={assetFilter} onValueChange={setAssetFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="All assets" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All assets</SelectItem>
              {uniqueAssets.map((asset) => (
                <SelectItem key={asset} value={asset}>
                  {asset}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={directionFilter} onValueChange={setDirectionFilter}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="All directions" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All directions</SelectItem>
              <SelectItem value="buy">Buy</SelectItem>
              <SelectItem value="sell">Sell</SelectItem>
            </SelectContent>
          </Select>
        </SearchToolbar>
        <DateRangeFilter
          value={dateRange}
          onChange={setDateRange}
          minDate={run.config.start_date}
          maxDate={run.config.end_date}
        />
      </div>

      <p className="text-muted-foreground text-sm">
        {filteredTrades.length === tradesWithAttribution.length
          ? `${filteredTrades.length} trades`
          : `${filteredTrades.length} of ${tradesWithAttribution.length} trades`}
      </p>

      {filteredTrades.length === 0 ? (
        <EmptyState title="No matching trades" />
      ) : (
        <VirtualDataTable
          columns={columns}
          data={filteredTrades}
          estimateRowSize={40}
          maxHeight={500}
          sorting
          columnVisibility={columnVisibility}
          onColumnVisibilityChange={setColumnVisibility}
          getRowClassName={getRowClassName}
          getRowId={(t, i) => `${i}-${t.date}-${t.asset_id}`}
          toolbar={(table) => (
            <>
              <ColumnVisibilityToggle table={table} />
              <Button variant="outline" size="sm" onClick={handleExportCsv}>
                <Download className="mr-1.5 size-4" />
                Export CSV
              </Button>
            </>
          )}
        />
      )}

      <TradeFrequencyChart trades={run.trades} />
    </div>
  );
}
