import { useState, useMemo, useEffect } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

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

type SortDir = 'asc' | 'desc' | null

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  filterPlaceholder = 'Filter...',
  filterKeys,
  pageSize = 25,
  className,
  rowClassName,
}: DataTableProps<T>) {
  const [filter, setFilter] = useState('')
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>(null)
  const [page, setPage] = useState(1)
  const [selectedPageSize, setSelectedPageSize] = useState<PageSizeOption>(
    () => toPageSizeOption(pageSize)
  )

  const safeData = data ?? []
  const searchKeys = filterKeys ?? columns.map(c => c.key)

  // Reset to page 1 when filter or sort changes
  useEffect(() => { setPage(1) }, [filter, sortKey, sortDir])

  const filtered = useMemo(() => {
    if (!filter.trim()) return safeData
    const q = filter.toLowerCase()
    return safeData.filter(row =>
      searchKeys.some(k => String(row[k] ?? '').toLowerCase().includes(q))
    )
  }, [safeData, filter, searchKeys])

  const sorted = useMemo(() => {
    if (!sortKey || !sortDir) return filtered ?? []
    return [...(filtered ?? [])].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av ?? '').localeCompare(String(bv ?? ''))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [filtered, sortKey, sortDir])

  const totalRows = sorted.length
  const totalPages = selectedPageSize === 'all' ? 1 : Math.ceil(totalRows / (selectedPageSize as number))
  // clamp page in case filter shrinks result set
  const currentPage = Math.min(page, Math.max(1, totalPages))

  const paginated = useMemo(() => {
    if (selectedPageSize === 'all') return sorted
    const sz = selectedPageSize as number
    const start = (currentPage - 1) * sz
    return sorted.slice(start, start + sz)
  }, [sorted, selectedPageSize, currentPage])

  // "1–25 of 119" range label
  const rangeStart = totalRows === 0 ? 0 : (selectedPageSize === 'all' ? 1 : (currentPage - 1) * (selectedPageSize as number) + 1)
  const rangeEnd   = selectedPageSize === 'all' ? totalRows : Math.min(currentPage * (selectedPageSize as number), totalRows)

  function toggleSort(key: string) {
    if (sortKey !== key) { setSortKey(key); setSortDir('asc') }
    else if (sortDir === 'asc') setSortDir('desc')
    else { setSortKey(null); setSortDir(null) }
  }

  function handlePageSizeChange(size: PageSizeOption) {
    setSelectedPageSize(size)
    setPage(1)
  }

  return (
    <div className={cn('space-y-3', className)}>
      <input
        type="text"
        placeholder={filterPlaceholder}
        value={filter}
        onChange={e => setFilter(e.target.value)}
        className="w-full max-w-sm rounded border border-hf-border bg-hf-surface px-3 py-1.5 text-sm text-hf-fg1 placeholder:text-hf-fg4 focus:outline-none focus:ring-1 focus:ring-hf-fg1"
        aria-label="Filter table"
      />
      <div className="rounded-lg border border-hf-border bg-hf-surface overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map(col => (
                <TableHead
                  key={col.key}
                  className={cn(
                    'text-xs text-hf-fg3 font-sans font-medium',
                    col.sortable && 'cursor-pointer select-none hover:text-hf-fg1',
                    col.className
                  )}
                  onClick={col.sortable ? () => toggleSort(col.key) : undefined}
                >
                  {col.header}
                  {col.sortable && sortKey === col.key && (
                    <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginated.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-8 text-center text-sm text-hf-fg4">
                  No results
                </TableCell>
              </TableRow>
            ) : (
              paginated.map((row, i) => (
                <TableRow key={i} className={rowClassName?.(row)}>
                  {columns.map(col => (
                    <TableCell key={col.key} className={cn('text-sm text-hf-fg2', col.className)}>
                      {col.render
                        ? col.render(row[col.key], row)
                        : String(row[col.key] ?? '')}
                    </TableCell>
                  ))}
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
            {selectedPageSize !== 'all' && totalPages > 1 && (
              <>
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  aria-label="Previous page"
                  className="disabled:opacity-30 hover:text-hf-fg1 transition-colors"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
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
