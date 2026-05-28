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

type PageSizeOption = 10 | 25 | 50 | 'all'
const PAGE_SIZE_OPTIONS: PageSizeOption[] = [10, 25, 50, 'all']

function toPageSizeOption(n: number): PageSizeOption {
  return ([10, 25, 50] as number[]).includes(n) ? (n as PageSizeOption) : 25
}

interface DataTableProps<T extends Record<string, unknown>> {
  data: T[]
  columns: ColumnDef<T>[]
  filterPlaceholder?: string
  filterKeys?: (keyof T & string)[]   // which fields to search in (used only if filterable is false)
  pageSize?: number                    // initial page size; must be 10 | 25 | 50 — defaults to 25
  className?: string
  rowClassName?: (row: T) => string    // for per-row styling (e.g. hub gene highlight)
  sortable?: boolean                   // when false, disable all column sorting (default: true)
  filterable?: boolean                 // when true, show per-column filter inputs below each header (default: false)
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  filterPlaceholder: _filterPlaceholder = 'Filter...',
  filterKeys: _filterKeys,
  pageSize = 25,
  className,
  rowClassName,
  sortable = true,
  filterable = false,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [selectedPageSize, setSelectedPageSize] = useState<PageSizeOption>(
    () => toPageSizeOption(pageSize)
  )
  const [pagination, setPagination] = useState<PaginationState>(() => ({
    pageIndex: 0,
    pageSize: toPageSizeOption(pageSize) === 'all' ? 999999 : (toPageSizeOption(pageSize) as number),
  }))

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

  const isPaginated = selectedPageSize !== 'all'

  const table = useReactTable({
    data: safeData,
    columns: tanstackColumns,
    state: {
      sorting,
      columnFilters,
      pagination,
    },
    // Always sort asc first on first click (consistent regardless of column type)
    sortDescFirst: false,
    onSortingChange: (updater) => {
      setSorting(prev => typeof updater === 'function' ? updater(prev) : updater)
      // reset to first page on sort change
      setPagination(prev => ({ ...prev, pageIndex: 0 }))
    },
    onColumnFiltersChange: (updater) => {
      setColumnFilters(prev => typeof updater === 'function' ? updater(prev) : updater)
      setPagination(prev => ({ ...prev, pageIndex: 0 }))
    },
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: true,
  })

  const { pageIndex } = table.getState().pagination
  const totalRows = table.getFilteredRowModel().rows.length
  const currentPageSize = isPaginated ? pagination.pageSize : totalRows
  const totalPages = isPaginated ? Math.ceil(totalRows / currentPageSize) : 1

  function handlePageSizeChange(size: PageSizeOption) {
    setSelectedPageSize(size)
    const numericSize = size === 'all' ? 999999 : (size as number)
    setPagination({ pageIndex: 0, pageSize: numericSize })
  }

  const rows = table.getPaginationRowModel().rows

  return (
    <div className={cn('space-y-3', className)}>
      <div className="rounded-lg border border-hf-border bg-hf-surface overflow-hidden">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(headerGroup => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header, i) => {
                  const colDef = columns[i]
                  const isSorted = header.column.getIsSorted()
                  const canSort = sortable && (colDef?.sortable ?? false)
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        'text-xs text-hf-fg3 font-sans font-medium',
                        canSort && 'cursor-pointer select-none hover:text-hf-fg1',
                        colDef?.className
                      )}
                      onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
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
                  {row.getVisibleCells().map((cell, i) => {
                    const colDef = columns[i]
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

      {/* Pagination footer — shown whenever there is data */}
      {totalRows > 0 && (
        <div className="flex items-center justify-between gap-4 text-xs text-hf-fg3">
          {/* Page size selector */}
          <div className="flex items-center gap-0.5">
            <span className="mr-1.5">Rows:</span>
            {PAGE_SIZE_OPTIONS.map(size => (
              <button
                key={String(size)}
                onClick={() => handlePageSizeChange(size)}
                className={cn(
                  'px-2 py-0.5 rounded border transition-colors',
                  selectedPageSize === size
                    ? 'border-hf-border text-hf-fg1 font-medium'
                    : 'border-transparent hover:text-hf-fg1'
                )}
              >
                {size === 'all' ? 'All' : size}
              </button>
            ))}
          </div>

          {/* Page X of Y + prev/next navigation */}
          <div className="flex items-center gap-1.5">
            <span className="tabular-nums">
              {isPaginated
                ? `Page ${pageIndex + 1} of ${totalPages}`
                : `${totalRows} rows`}
            </span>
            {isPaginated && totalPages > 1 && (
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
