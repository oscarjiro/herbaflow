import * as React from "react";
import { type Table } from "@tanstack/react-table";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from "lucide-react";

import { cn } from "@/lib/cn";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * DataTablePager — the full pager for DataTable.
 *
 * It owns NO sorting / pagination state of its own. It reads the row count,
 * current page and page size from the TanStack `table` instance passed in, and
 * commands navigation through that same instance. This keeps one canonical
 * source of pagination state (the TanStack table inside DataTable), never a
 * parallel reimplementation.
 *
 * Controls (per the mockup .pager): first / prev / type-a-page jump / next /
 * last, plus a rows-per-page selector reusing the Select component. The "All"
 * option sets the page size to the full row count so every row renders on one
 * page.
 */

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const ALL_VALUE = "all";

function PagerButton({ className, ...props }: React.ComponentProps<"button">) {
  return (
    <button
      type="button"
      className={cn(
        // Mockup .pbtn — 30px square, small radius, surface fill, hf border.
        "border-hf-border bg-hf-surface text-hf-fg-2 inline-flex size-[30px] items-center justify-center rounded-[var(--radius-sm)] border transition-colors",
        "hover:border-hf-fg-3 hover:text-hf-fg-1 hover:bg-hf-surface-2",
        "outline-none focus-visible:ring-[2px] focus-visible:ring-[color-mix(in_srgb,var(--hf-fg-1),transparent_55%)]",
        "disabled:hover:border-hf-border disabled:hover:bg-hf-surface disabled:hover:text-hf-fg-2 disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
      {...props}
    />
  );
}

export function DataTablePager<T>({ table }: { table: Table<T> }) {
  const totalRows = table.getRowCount();
  const pageCount = table.getPageCount();
  const pageIndex = table.getState().pagination.pageIndex;
  const pageSize = table.getState().pagination.pageSize;
  const currentPage = pageIndex + 1;

  // The rows-per-page selector value: a numeric string for a fixed size, or
  // "all" when the page size has been widened to the full row count.
  const sizeValue =
    pageSize >= totalRows && totalRows > 0 && !PAGE_SIZE_OPTIONS.includes(pageSize as never)
      ? ALL_VALUE
      : String(pageSize);

  // Range read-out: "Showing X–Y of N".
  const firstRow = totalRows === 0 ? 0 : pageIndex * pageSize + 1;
  const lastRow = Math.min((pageIndex + 1) * pageSize, totalRows);

  // The page-jump input is locally controlled so a user can type freely; the
  // table only navigates on commit (Enter / blur), clamped to a valid page.
  const [draftPage, setDraftPage] = React.useState(String(currentPage));
  React.useEffect(() => {
    setDraftPage(String(currentPage));
  }, [currentPage]);

  function commitJump() {
    const parsed = Number.parseInt(draftPage, 10);
    if (Number.isNaN(parsed)) {
      setDraftPage(String(currentPage));
      return;
    }
    const clamped = Math.min(Math.max(parsed, 1), Math.max(pageCount, 1));
    table.setPageIndex(clamped - 1);
    setDraftPage(String(clamped));
  }

  function handleSizeChange(value: string) {
    if (value === ALL_VALUE) {
      table.setPageSize(totalRows || 1);
    } else {
      table.setPageSize(Number(value));
    }
  }

  return (
    <div
      data-slot="datatable-pager"
      className="border-hf-border text-hf-fg-3 flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm"
    >
      <span className="num tabular-nums">
        Showing {firstRow}
        {"–"}
        {lastRow} of {totalRows}
      </span>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="dt-page-size" className="whitespace-nowrap">
            Rows per page
          </label>
          <Select value={sizeValue} onValueChange={handleSizeChange}>
            <SelectTrigger
              id="dt-page-size"
              size="sm"
              aria-label="Rows per page"
              className="w-[5.25rem]"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZE_OPTIONS.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n}
                </SelectItem>
              ))}
              <SelectItem value={ALL_VALUE}>All</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <PagerButton
            aria-label="First page"
            onClick={() => table.setPageIndex(0)}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronsLeftIcon className="size-4" aria-hidden="true" />
          </PagerButton>
          <PagerButton
            aria-label="Previous page"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronLeftIcon className="size-4" aria-hidden="true" />
          </PagerButton>

          <span className="flex items-center gap-1.5 whitespace-nowrap">
            Page
            <input
              id="dt-page-jump"
              aria-label="Page number"
              inputMode="numeric"
              className={cn(
                "border-hf-border-strong bg-hf-surface text-hf-fg-1 num w-[46px] rounded-[var(--radius-sm)] border px-1.5 py-1 text-center tabular-nums",
                "outline-none focus-visible:ring-[2px] focus-visible:ring-[color-mix(in_srgb,var(--hf-fg-1),transparent_55%)]",
              )}
              value={draftPage}
              onChange={(e) => setDraftPage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commitJump();
                }
              }}
              onBlur={commitJump}
            />
            of {Math.max(pageCount, 1)}
          </span>

          <PagerButton
            aria-label="Next page"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            <ChevronRightIcon className="size-4" aria-hidden="true" />
          </PagerButton>
          <PagerButton
            aria-label="Last page"
            onClick={() => table.setPageIndex(pageCount - 1)}
            disabled={!table.getCanNextPage()}
          >
            <ChevronsRightIcon className="size-4" aria-hidden="true" />
          </PagerButton>
        </div>
      </div>
    </div>
  );
}
