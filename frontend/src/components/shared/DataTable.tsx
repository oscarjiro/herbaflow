import { useState, useMemo } from 'react'
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

interface DataTableProps<T extends Record<string, unknown>> {
  data: T[]
  columns: ColumnDef<T>[]
  filterPlaceholder?: string
  filterKeys?: (keyof T & string)[]   // which fields to search in
  pageSize?: number                    // default 50
  className?: string
  rowClassName?: (row: T) => string    // for per-row styling (e.g. hub gene highlight)
}

type SortDir = 'asc' | 'desc' | null

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  filterPlaceholder = 'Filter...',
  filterKeys,
  pageSize = 50,
  className,
  rowClassName,
}: DataTableProps<T>) {
  const [filter, setFilter] = useState('')
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>(null)
  const [showAll, setShowAll] = useState(false)

  const searchKeys = filterKeys ?? columns.map(c => c.key)

  const filtered = useMemo(() => {
    if (!filter.trim()) return data
    const q = filter.toLowerCase()
    return data.filter(row =>
      searchKeys.some(k => String(row[k] ?? '').toLowerCase().includes(q))
    )
  }, [data, filter, searchKeys])

  const sorted = useMemo(() => {
    if (!sortKey || !sortDir) return filtered
    return [...filtered].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av ?? '').localeCompare(String(bv ?? ''))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [filtered, sortKey, sortDir])

  const paginated = showAll ? sorted : sorted.slice(0, pageSize)

  function toggleSort(key: string) {
    if (sortKey !== key) { setSortKey(key); setSortDir('asc') }
    else if (sortDir === 'asc') setSortDir('desc')
    else { setSortKey(null); setSortDir(null) }
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
      {sorted.length > pageSize && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="text-xs text-hf-fg3 hover:text-hf-fg1 underline underline-offset-2"
        >
          Show all {sorted.length} rows
        </button>
      )}
    </div>
  )
}
