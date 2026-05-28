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
  type FilterFn,
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
  filterKeys?: (keyof T & string)[]   // which fields to search in
  pageSize?: number                    // initial page size; must be 10 | 25 | 50 — defaults to 25
  className?: string
  rowClassName?: (row: T) => string    // for per-row styling (e.g. hub gene highlight)
}

// Custom global filter function that respects filterKeys
function buildGlobalFilter<T extends Record<string, unknown>>(
  filterKeys: (keyof T & string)[]
): FilterFn<T> {
  const fn: FilterFn<T> = (row, _columnId, filterValue: string) => {
    if (!filterValue || !filterValue.trim()) return true
    const q = filterValue.toLowerCase()
    return filterKeys.some(k => String((row.original as T)[k] ?? '').toLowerCase().includes(q))
  }
  fn.autoRemove = (val: unknown) => !val || !(val as string).trim()
  return fn
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  filterPlaceholder = 'Filter...',
  filterKeys,
  pageSize = 25,
  className,
  rowClassName,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState('')
  const [selectedPageSize, setSelectedPageSize] = useState<PageSizeOption>(
    () => toPageSizeOption(pageSize)
  )
  const [pagination, setPagination] = useState<PaginationState>(() => ({
    pageIndex: 0,
    pageSize: toPageSizeOption(pageSize) === 'all' ? 999999 : (toPageSizeOption(pageSize) as number),
  }))

  const safeData = useMemo(() => data ?? [], [data])
  const searchKeys = useMemo(
    () => filterKeys ?? columns.map(c => c.key),
    [filterKeys, columns]
  )

  // Build TanStack ColumnDef array from our public ColumnDef interface
  const tanstackColumns = useMemo<TanStackColumnDef<T, unknown>[]>(() => {
    return columns.map(col => ({
      id: col.key,
      accessorKey: col.key,
      header: col.header,
      enableSorting: col.sortable ?? false,
      enableGlobalFilter: true,
      cell: col.render
        ? ({ row }: { row: { original: T } }) => col.render!(row.original[col.key], row.original)
        : ({ getValue }: { getValue: () => unknown }) => String(getValue() ?? ''),
    }))
  }, [columns])

  const globalFilterFn = useMemo(
    () => buildGlobalFilter<T>(searchKeys),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searchKeys.join(',')]
  )

  const isPaginated = selectedPageSize !== 'all'

  const table = useReactTable({
    data: safeData,
    columns: tanstackColumns,
    state: {
      sorting,
      globalFilter,
      pagination,
    },
    // Always sort asc first on first click (consistent regardless of column type)
    sortDescFirst: false,
    onSortingChange: (updater) => {
      setSorting(prev => typeof updater === 'function' ? updater(prev) : updater)
      // reset to first page on sort change
      setPagination(prev => ({ ...prev, pageIndex: 0 }))
    },
    onGlobalFilterChange: (updater) => {
      const next = typeof updater === 'function' ? updater(globalFilter) : updater
      setGlobalFilter(next)
      setPagination(prev => ({ ...prev, pageIndex: 0 }))
    },
    onPaginationChange: setPagination,
    globalFilterFn,
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

  const rangeStart = totalRows === 0 ? 0 : pageIndex * currentPageSize + 1
  const rangeEnd = isPaginated
    ? Math.min((pageIndex + 1) * currentPageSize, totalRows)
    : totalRows

  function handlePageSizeChange(size: PageSizeOption) {
    setSelectedPageSize(size)
    const numericSize = size === 'all' ? 999999 : (size as number)
    setPagination({ pageIndex: 0, pageSize: numericSize })
  }

  const rows = table.getPaginationRowModel().rows

  return (
    <div className={cn('space-y-3', className)}>
      <input
        type="text"
        placeholder={filterPlaceholder}
        value={globalFilter}
        onChange={e => {
          setGlobalFilter(e.target.value)
          setPagination(prev => ({ ...prev, pageIndex: 0 }))
        }}
        className="w-full max-w-sm rounded border border-hf-border bg-hf-surface px-3 py-1.5 text-sm text-hf-fg1 placeholder:text-hf-fg4 focus:outline-none focus:ring-1 focus:ring-hf-fg1"
        aria-label="Filter table"
      />
      <div className="rounded-lg border border-hf-border bg-hf-surface overflow-hidden">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(headerGroup => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header, i) => {
                  const colDef = columns[i]
                  const isSorted = header.column.getIsSorted()
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        'text-xs text-hf-fg3 font-sans font-medium',
                        colDef?.sortable && 'cursor-pointer select-none hover:text-hf-fg1',
                        colDef?.className
                      )}
                      onClick={colDef?.sortable ? header.column.getToggleSortingHandler() : undefined}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {isSorted && (
                        <span className="ml-1" data-sort-indicator="">
                          {isSorted === 'asc' ? '↑' : '↓'}
                        </span>
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

          {/* Row range + prev/next navigation */}
          <div className="flex items-center gap-1.5">
            <span className="tabular-nums">
              {totalRows === 0 ? '0 rows' : `${rangeStart}–${rangeEnd} of ${totalRows}`}
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
