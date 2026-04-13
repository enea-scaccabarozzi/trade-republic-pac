import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import type { RowSelectionState } from "@tanstack/react-table";
import { Plus, RefreshCw } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { BatchActionBar } from "@/components/dashboard/batch-action-bar";
import { createRunsColumns } from "@/components/dashboard/runs-columns";
import { SummaryBar } from "@/components/dashboard/summary-bar";
import { DataTable } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { SearchToolbar } from "@/components/search-toolbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";
import { useDeleteRuns, useRuns } from "@/hooks/use-runs";

export const Route = createFileRoute("/")({
  component: DashboardHome,
});

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholders never reorder
          <Skeleton key={`kpi-${i}`} className="h-[104px] rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-10 w-full max-w-sm" />
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        {Array.from({ length: 5 }, (_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholders never reorder
          <Skeleton key={`row-${i}`} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}

export function DashboardHome() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useRuns();
  const deleteRuns = useDeleteRuns();

  const [search, setSearch] = useState("");
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [deleteTarget, setDeleteTarget] = useState<{
    ids: string[];
    mode: "single" | "batch";
  } | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);

  useKeyboardShortcuts([
    {
      keys: "n",
      handler: () => navigate({ to: "/run" }),
      description: "New backtest",
    },
    {
      keys: "/",
      handler: () => searchInputRef.current?.focus(),
      description: "Focus search",
    },
    {
      keys: "Escape",
      handler: () => {
        if (search) setSearch("");
        else searchInputRef.current?.blur();
      },
      description: "Clear search",
    },
  ]);

  const runs = data?.runs ?? [];
  const filteredRuns = search
    ? runs.filter((r) => r.strategy.toLowerCase().includes(search.toLowerCase()))
    : runs;

  const columns = useMemo(
    () =>
      createRunsColumns({
        onView: (id) => navigate({ to: "/runs/$id", params: { id } }),
        onClone: (id) => navigate({ to: "/run", search: { clone: id } }),
        onDelete: (id) => setDeleteTarget({ ids: [id], mode: "single" }),
      }),
    [navigate],
  );

  const selectedIds = Object.keys(rowSelection).filter((k) => rowSelection[k]);
  const selectedCount = selectedIds.length;

  const isEmpty = !isLoading && !isError && runs.length === 0;
  const hasData = !isLoading && !isError && runs.length > 0;

  const handleBatchCompare = () => {
    navigate({ to: "/compare", search: { ids: selectedIds.join(",") } });
  };

  const handleBatchDelete = () => {
    setDeleteTarget({ ids: selectedIds, mode: "batch" });
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteRuns.mutateAsync(deleteTarget.ids);
      setRowSelection({});
      setDeleteTarget(null);
    } catch {
      window.alert("Failed to delete runs. Please try again.");
    }
  };

  const deleteDescription =
    deleteTarget?.mode === "batch"
      ? `This will permanently delete ${deleteTarget.ids.length} runs. This action cannot be undone.`
      : "This will permanently delete this run. This action cannot be undone.";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Strategy validation workbench"
        actions={
          <Button asChild>
            <Link to="/run">
              <Plus className="mr-1.5 size-4" />
              Run Backtest
            </Link>
          </Button>
        }
      />

      {isLoading && <DashboardSkeleton />}

      {isError && (
        <Card className="border-destructive">
          <CardContent className="flex items-center justify-between py-4">
            <p className="text-destructive text-sm">
              Failed to load runs
              {error instanceof Error ? `: ${error.message}` : ""}
            </p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="mr-1.5 size-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {isEmpty && (
        <EmptyState
          title="No backtests yet"
          description="Run your first backtest to see results here."
          action={{
            label: "Run your first backtest",
            onClick: () => navigate({ to: "/run" }),
          }}
        />
      )}

      {hasData && (
        <>
          <SummaryBar runs={runs} />
          <SearchToolbar
            ref={searchInputRef}
            value={search}
            onChange={setSearch}
            placeholder="Search strategies…"
          />
          <DataTable
            columns={columns}
            data={filteredRuns}
            sorting
            initialSorting={[{ id: "created_at", desc: true }]}
            selectable
            rowSelection={rowSelection}
            onRowSelectionChange={setRowSelection}
            getRowId={(row) => row.run_id}
            onRowClick={(row) => navigate({ to: "/runs/$id", params: { id: row.run_id } })}
            pageSize={20}
            emptyState={<EmptyState title="No matching runs" />}
          />
          <BatchActionBar
            selectedCount={selectedCount}
            onCompare={handleBatchCompare}
            onDelete={handleBatchDelete}
            onClearSelection={() => setRowSelection({})}
          />
        </>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete Run"
        description={deleteDescription}
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        loading={deleteRuns.isPending}
      />
    </div>
  );
}
