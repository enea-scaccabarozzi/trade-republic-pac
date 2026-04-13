import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  type OnChangeFn,
  type SortingState,
  type Table,
  useReactTable,
  type VisibilityState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef, useState } from "react";
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface VirtualDataTableProps<TData> {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];
  estimateRowSize?: number;
  maxHeight?: number;
  sorting?: boolean;
  emptyState?: React.ReactNode;
  columnVisibility?: VisibilityState;
  onColumnVisibilityChange?: OnChangeFn<VisibilityState>;
  getRowId?: (row: TData, index: number) => string;
  toolbar?: (table: Table<TData>) => React.ReactNode;
  getRowClassName?: (row: TData) => string;
  className?: string;
}

export function VirtualDataTable<TData>({
  columns,
  data,
  estimateRowSize = 40,
  maxHeight = 600,
  sorting: enableSorting = false,
  emptyState,
  columnVisibility: externalColumnVisibility,
  onColumnVisibilityChange,
  getRowId,
  toolbar,
  getRowClassName,
  className,
}: VirtualDataTableProps<TData>) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [sortingState, setSortingState] = useState<SortingState>([]);

  const table = useReactTable<TData>({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(enableSorting && {
      onSortingChange: setSortingState,
      getSortedRowModel: getSortedRowModel(),
    }),
    getFilteredRowModel: getFilteredRowModel(),
    ...(getRowId && { getRowId }),
    onColumnVisibilityChange,
    state: {
      sorting: sortingState,
      ...(externalColumnVisibility && {
        columnVisibility: externalColumnVisibility,
      }),
    },
  });

  const { rows } = table.getRowModel();

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateRowSize,
    overscan: 20,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const firstItem = virtualItems[0];
  const lastItem = virtualItems[virtualItems.length - 1];

  const paddingTop = firstItem ? firstItem.start : 0;
  const paddingBottom = lastItem ? totalSize - lastItem.end : 0;

  const visibleColumns = table.getVisibleLeafColumns().length;

  return (
    <div className={cn("space-y-4", className)}>
      {toolbar && <div className="flex items-center gap-2">{toolbar(table)}</div>}
      <div className="rounded-md border">
        <div ref={parentRef} className="overflow-auto" style={{ maxHeight }}>
          <table className="w-full caption-bottom text-sm">
            <TableHeader className="sticky top-0 z-10 bg-background">
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={visibleColumns} className="h-24 text-center">
                    {emptyState ?? "No results."}
                  </TableCell>
                </TableRow>
              ) : (
                <>
                  {paddingTop > 0 && (
                    <tr>
                      <td colSpan={visibleColumns} style={{ height: `${paddingTop}px` }} />
                    </tr>
                  )}
                  {virtualItems.map((virtualRow) => {
                    const row = rows[virtualRow.index];
                    if (!row) return null;
                    return (
                      <TableRow
                        key={row.id}
                        className={getRowClassName ? getRowClassName(row.original) : undefined}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id}>
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                  {paddingBottom > 0 && (
                    <tr>
                      <td colSpan={visibleColumns} style={{ height: `${paddingBottom}px` }} />
                    </tr>
                  )}
                </>
              )}
            </TableBody>
          </table>
        </div>
      </div>
    </div>
  );
}
