import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef as TanStackColumnDef,
  type SortingState,
  type PaginationState,
  type ColumnFiltersState,
} from '@tanstack/react-table'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

// Public interface — unchanged so all stage panels work without modification
export interface ColumnDef<T> {
  key: keyof T & string
  header: string
  sortable?: boolean
  enableColumnFilter?: boolean
  render?: (value: T[keyof T], row: T) => React.ReactNode
  className?: string
}

interface DataTableProps<T extends Record<string, unknown>> {
  data: T[]
  columns: ColumnDef<T>[]
  pageSize?: number                    // when set, enables pagination with this page size; omit to show all rows
  className?: string
  rowClassName?: (row: T) => string    // for per-row styling (e.g. hub gene highlight)
  sortable?: boolean                   // when false, disable all column sorting (default: true)
  filterable?: boolean                 // when true, show per-column filter inputs below each header (default: false)
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  pageSize,
  className,
  rowClassName,
  sortable = true,
  filterable = false,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [pagination, setPagination] = useState<PaginationState>(() => ({
    pageIndex: 0,
    pageSize: pageSize ?? 999999,
  }))

  const isPaginated = pageSize !== undefined

  const safeData = useMemo(() => data ?? [], [data])

  // Build TanStack ColumnDef array from our public ColumnDef interface
  const tanstackColumns = useMemo<TanStackColumnDef<T, unknown>[]>(() => {
    return columns.map(col => ({
      id: col.key,
      accessorKey: col.key,
      header: col.header,
      enableSorting: sortable && (col.sortable ?? false),
      enableColumnFilter: filterable && (col.enableColumnFilter ?? true),
      cell: col.render
        ? ({ row }: { row: { original: T } }) => col.render!(row.original[col.key], row.original)
        : ({ getValue }: { getValue: () => unknown }) => String(getValue() ?? ''),
    }))
  }, [columns, sortable, filterable])

  const table = useReactTable({
    data: safeData,
    columns: tanstackColumns,
    state: {
      sorting,
      columnFilters,
      ...(isPaginated ? { pagination } : {}),
    },
    // Always sort asc first on first click (consistent regardless of column type)
    sortDescFirst: false,
    onSortingChange: (updater) => {
      setSorting(prev => typeof updater === 'function' ? updater(prev) : updater)
    },
    onColumnFiltersChange: (updater) => {
      setColumnFilters(prev => typeof updater === 'function' ? updater(prev) : updater)
    },
    ...(isPaginated ? { onPaginationChange: setPagination } : {}),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    ...(isPaginated ? { getPaginationRowModel: getPaginationRowModel() } : {}),
    autoResetPageIndex: true,
  })

  const totalRows = table.getFilteredRowModel().rows.length
  const pageIndex = isPaginated ? table.getState().pagination.pageIndex : 0
  const totalPages = isPaginated ? Math.ceil(totalRows / pageSize) : 1

  const rows = isPaginated
    ? table.getPaginationRowModel().rows
    : table.getRowModel().rows

  return (
    <div className={cn('space-y-3', className)}>
      <div className="rounded-lg border border-hf-border bg-hf-surface overflow-hidden">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(headerGroup => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map(header => {
                  const colDef = columns.find(c => c.key === header.column.id)
                  const isSorted = header.column.getIsSorted()
                  const canSort = sortable && (colDef?.sortable ?? false)
                  const sortHandler = header.column.getToggleSortingHandler()
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        'text-xs text-hf-fg3 font-sans font-medium',
                        canSort && 'cursor-pointer select-none hover:text-hf-fg1',
                        colDef?.className
                      )}
                      onClick={canSort ? sortHandler : undefined}
                      {...(canSort ? {
                        tabIndex: 0,
                        role: 'button',
                        'aria-sort': isSorted === 'asc' ? 'ascending' : isSorted === 'desc' ? 'descending' : 'none',
                        onKeyDown: (e: React.KeyboardEvent) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            sortHandler?.(e as unknown as React.MouseEvent)
                          }
                        },
                      } : {})}
                    >
                      <div>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {isSorted && (
                          <span className="ml-1" data-sort-indicator="">
                            {isSorted === 'asc' ? '↑' : '↓'}
                          </span>
                        )}
                      </div>
                      {filterable && header.column.getCanFilter() && (
                        <input
                          type="text"
                          placeholder={`Filter ${typeof header.column.columnDef.header === 'string' ? header.column.columnDef.header : header.column.id}`}
                          value={(header.column.getFilterValue() as string) ?? ''}
                          onChange={e => header.column.setFilterValue(e.target.value || undefined)}
                          onClick={e => e.stopPropagation()}
                          className="mt-1 w-full rounded border border-hf-border bg-hf-surface px-2 py-0.5 text-xs text-hf-fg1 placeholder:text-hf-fg4 focus:outline-none focus:ring-1 focus:ring-hf-fg1 font-normal cursor-text"
                          aria-label={`Filter ${header.column.id}`}
                        />
                      )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-8 text-center text-sm text-hf-fg4">
                  No results
                </TableCell>
              </TableRow>
            ) : (
              rows.map(row => (
                <TableRow key={row.id} className={rowClassName?.(row.original)}>
                  {row.getVisibleCells().map(cell => {
                    const colDef = columns.find(c => c.key === cell.column.id)
                    return (
                      <TableCell key={cell.id} className={cn('text-sm text-hf-fg2', colDef?.className)}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    )
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination footer — shown only when pageSize is set and there is data */}
      {isPaginated && totalRows > 0 && (
        <div className="flex items-center justify-end gap-4 text-xs text-hf-fg3">
          {/* Page X of Y + prev/next navigation */}
          <div className="flex items-center gap-1.5">
            <span className="tabular-nums">
              {`Page ${pageIndex + 1} of ${totalPages}`}
            </span>
            {totalPages > 1 && (
              <>
                <button
                  onClick={() => setPagination(prev => ({ ...prev, pageIndex: Math.max(0, prev.pageIndex - 1) }))}
                  disabled={pageIndex === 0}
                  aria-label="Previous page"
                  className="disabled:opacity-30 hover:text-hf-fg1 transition-colors"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setPagination(prev => ({ ...prev, pageIndex: Math.min(totalPages - 1, prev.pageIndex + 1) }))}
                  disabled={pageIndex >= totalPages - 1}
                  aria-label="Next page"
                  className="disabled:opacity-30 hover:text-hf-fg1 transition-colors"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default DataTable
