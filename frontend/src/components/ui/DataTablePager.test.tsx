/**
 * DataTablePager — full pager driven by a TanStack `table` instance.
 *
 * The pager owns NO sorting/pagination state of its own: it reads from and
 * commands the TanStack `table` passed in as a prop. We mount it through a tiny
 * harness that builds a real `useReactTable` instance so the controls drive
 * genuine pagination behavior.
 *
 * Controls under test: first / prev / page-jump input / next / last + a
 * rows-per-page Select (Task-7) with 10/20/50/All options.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import {
  type ColumnDef,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { DataTablePager } from "./DataTablePager";

type Row = { gene: string; score: number };
const cols: ColumnDef<Row>[] = [
  { accessorKey: "gene", header: "Gene" },
  { accessorKey: "score", header: "Score" },
];

/** Harness: a live table + the pager + a visible read-out of the current page rows. */
function Harness({ data, initialPageSize = 10 }: { data: Row[]; initialPageSize?: number }) {
  const table = useReactTable({
    data,
    columns: cols,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: initialPageSize } },
  });

  return (
    <div>
      <ul data-testid="page-rows">
        {table.getRowModel().rows.map((r) => (
          <li key={r.id}>{r.original.gene}</li>
        ))}
      </ul>
      <DataTablePager table={table} />
    </div>
  );
}

function makeData(n: number): Row[] {
  return Array.from({ length: n }, (_, i) => ({ gene: `G${i}`, score: i }));
}

function visibleGenes(): string[] {
  return Array.from(screen.getByTestId("page-rows").querySelectorAll("li")).map(
    (li) => li.textContent ?? "",
  );
}

describe("DataTablePager — navigation", () => {
  it("renders accessible first/prev/next/last controls and a page-jump input", () => {
    render(<Harness data={makeData(35)} />);
    expect(screen.getByRole("button", { name: /first page/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /previous page/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next page/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /last page/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/page number/i)).toBeInTheDocument();
  });

  it("first/prev are disabled on the first page", () => {
    render(<Harness data={makeData(35)} />);
    expect(screen.getByRole("button", { name: /first page/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /previous page/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next page/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /last page/i })).toBeEnabled();
  });

  it("next advances to the second page", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);
    expect(visibleGenes()).toContain("G0");

    await user.click(screen.getByRole("button", { name: /next page/i }));

    expect(visibleGenes()).toContain("G10");
    expect(visibleGenes()).not.toContain("G0");
  });

  it("prev returns to the previous page", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);
    await user.click(screen.getByRole("button", { name: /next page/i }));
    await user.click(screen.getByRole("button", { name: /previous page/i }));
    expect(visibleGenes()).toContain("G0");
  });

  it("last jumps to the final page and disables next/last", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);
    await user.click(screen.getByRole("button", { name: /last page/i }));
    // 35 rows / 10 per page → last page has G30..G34
    expect(visibleGenes()).toContain("G34");
    expect(screen.getByRole("button", { name: /next page/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /last page/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /first page/i })).toBeEnabled();
  });

  it("first returns to page one", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);
    await user.click(screen.getByRole("button", { name: /last page/i }));
    await user.click(screen.getByRole("button", { name: /first page/i }));
    expect(visibleGenes()).toContain("G0");
  });
});

describe("DataTablePager — page-jump input", () => {
  it("navigates to a typed page number", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);
    const input = screen.getByLabelText(/page number/i);

    await user.clear(input);
    await user.type(input, "3");
    // commit the jump
    await user.keyboard("{Enter}");

    // Page 3 (1-indexed) → rows G20..G29
    expect(visibleGenes()).toContain("G20");
  });

  it("clamps an out-of-range page number to the last page", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);
    const input = screen.getByLabelText(/page number/i);

    await user.clear(input);
    await user.type(input, "99");
    await user.keyboard("{Enter}");

    // 4 pages total → clamp to page 4 (G30..G34)
    expect(visibleGenes()).toContain("G34");
  });
});

describe("DataTablePager — rows per page", () => {
  it("renders an accessible rows-per-page selector", () => {
    render(<Harness data={makeData(35)} />);
    expect(screen.getByRole("combobox", { name: /rows per page/i })).toBeInTheDocument();
  });

  it("changing rows-per-page updates how many rows render", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);
    expect(visibleGenes()).toHaveLength(10);

    await user.click(screen.getByRole("combobox", { name: /rows per page/i }));
    await user.click(screen.getByRole("option", { name: /^20$/ }));

    expect(visibleGenes()).toHaveLength(20);
  });

  it("choosing All shows every row", async () => {
    const user = userEvent.setup();
    render(<Harness data={makeData(35)} />);

    await user.click(screen.getByRole("combobox", { name: /rows per page/i }));
    await user.click(screen.getByRole("option", { name: /^all$/i }));

    expect(visibleGenes()).toHaveLength(35);
  });
});
