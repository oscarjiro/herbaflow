import { useState } from "react";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTablePager } from "@/components/ui/DataTablePager";
import { ColumnInfo } from "@/components/ui/ColumnInfo";
import { cn } from "@/lib/cn";
import "@/components/ui/dataTable.types";

export function DataTable<T>({
  columns,
  data,
  emptyMessage = "No results.",
}: {
  columns: ColumnDef<T>[];
  data: T[];
  emptyMessage?: string;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  if (data.length === 0) {
    return (
      <div data-slot="datatable" className="w-full">
        <div
          data-slot="datatable-empty"
          className="text-hf-fg-3 border-hf-border flex items-center justify-center rounded-[var(--radius-lg)] border border-dashed py-10 text-sm"
        >
          {emptyMessage}
        </div>
      </div>
    );
  }

  return (
    <div
      data-slot="datatable"
      className="border-hf-border bg-hf-surface w-full overflow-hidden rounded-[var(--radius-lg)] border"
    >
      <div className="scroll w-full overflow-x-auto max-md:[&_table]:block max-md:[&_tbody_tr]:mb-3 max-md:[&_tbody_tr]:block">
        <Table className="tabular-nums">
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => (
                  <TableHead
                    key={h.id}
                    className={cn(h.column.columnDef.meta?.className)}
                    aria-sort={
                      h.column.getIsSorted() === "asc"
                        ? "ascending"
                        : h.column.getIsSorted() === "desc"
                          ? "descending"
                          : "none"
                    }
                  >
                    <span className="inline-flex items-center gap-1">
                      {h.column.getCanSort() ? (
                        <button
                          type="button"
                          className="hover:text-hf-fg-1 inline-flex items-center gap-1 uppercase transition-colors"
                          onClick={h.column.getToggleSortingHandler()}
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          <span aria-hidden>
                            {h.column.getIsSorted() === "asc"
                              ? "↑"
                              : h.column.getIsSorted() === "desc"
                                ? "↓"
                                : ""}
                          </span>
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                      {h.column.columnDef.meta?.info ? (
                        <ColumnInfo
                          text={h.column.columnDef.meta.info}
                          label={
                            typeof h.column.columnDef.header === "string"
                              ? `About ${h.column.columnDef.header}`
                              : undefined
                          }
                        />
                      ) : null}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className={cn(cell.column.columnDef.meta?.className)}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <DataTablePager table={table} />
    </div>
  );
}
