import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "./DataTable";
import "@/components/ui/dataTable.types";

type Row = { gene: string; score: number };
const cols: ColumnDef<Row>[] = [
  { accessorKey: "gene", header: "Gene" },
  { accessorKey: "score", header: "Score" },
];

test("renders rows from data", () => {
  render(<DataTable columns={cols} data={[{ gene: "EGFR", score: 0.91 }]} />);
  expect(screen.getByText("EGFR")).toBeInTheDocument();
  expect(screen.getByText("0.91")).toBeInTheDocument();
});

test("sorts rows when a header is clicked", () => {
  render(
    <DataTable
      columns={cols}
      data={[
        { gene: "TP53", score: 0.2 },
        { gene: "EGFR", score: 0.9 },
      ]}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: /gene/i }));

  const rows = screen.getAllByRole("row").slice(1);
  expect(rows[0]).toHaveTextContent("EGFR");
  expect(rows[1]).toHaveTextContent("TP53");
});

test("paginates with a page-size control (default 10)", () => {
  const many = Array.from({ length: 12 }, (_, i) => ({ gene: `G${i}`, score: i }));
  render(<DataTable columns={cols} data={many} />);
  expect(screen.getAllByRole("row").slice(1)).toHaveLength(10);
  // The rows-per-page control is the Select component (an accessible combobox).
  expect(screen.getByRole("combobox", { name: /rows per page/i })).toBeInTheDocument();
});

test("shows every row when All is chosen", async () => {
  const user = userEvent.setup();
  const many = Array.from({ length: 12 }, (_, i) => ({ gene: `G${i}`, score: i }));
  render(<DataTable columns={cols} data={many} />);

  await user.click(screen.getByRole("combobox", { name: /rows per page/i }));
  await user.click(screen.getByRole("option", { name: /^all$/i }));

  expect(screen.getAllByRole("row").slice(1)).toHaveLength(12);
});

test("exposes a responsive container for mobile card-collapse", () => {
  const { container } = render(<DataTable columns={cols} data={[{ gene: "EGFR", score: 0.9 }]} />);

  expect(container.querySelector('[data-slot="datatable"]')).toBeInTheDocument();
});

test("shows the default empty-state message when data is empty", () => {
  const { container } = render(<DataTable columns={cols} data={[]} />);

  expect(screen.getByText("No results.")).toBeInTheDocument();
  expect(container.querySelector('[data-slot="datatable-empty"]')).toBeInTheDocument();
});

test("shows a custom emptyMessage when data is empty", () => {
  render(<DataTable columns={cols} data={[]} emptyMessage="No compounds yet." />);

  expect(screen.getByText("No compounds yet.")).toBeInTheDocument();
});

test("does not render pagination controls when data is empty", () => {
  render(<DataTable columns={cols} data={[]} />);

  expect(screen.queryByRole("combobox", { name: /rows per page/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /previous page/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /next page/i })).not.toBeInTheDocument();
});

test("does not render column headers when data is empty", () => {
  render(<DataTable columns={cols} data={[]} />);

  expect(screen.queryByText("Gene")).not.toBeInTheDocument();
  expect(screen.queryByText("Score")).not.toBeInTheDocument();
});

// ── meta.info — column info tooltip affordance ───────────────────────────────

type InfoRow = { gene: string; score: number };

test("column with meta.info renders a column-info button in the header", () => {
  const infoCols: ColumnDef<InfoRow>[] = [
    {
      accessorKey: "gene",
      header: "Gene",
      meta: { info: "HGNC gene symbol" },
    },
    { accessorKey: "score", header: "Score" },
  ];
  render(<DataTable columns={infoCols} data={[{ gene: "EGFR", score: 0.91 }]} />);

  // The ColumnInfo button should be present for the "Gene" column.
  const infoBtn = document.querySelector("[data-slot='column-info']");
  expect(infoBtn).toBeInTheDocument();
});

test("column with meta.info tooltip text is accessible (aria-label set)", () => {
  const infoCols: ColumnDef<InfoRow>[] = [
    {
      accessorKey: "gene",
      header: "Gene",
      meta: { info: "HGNC gene symbol" },
    },
    { accessorKey: "score", header: "Score" },
  ];
  render(<DataTable columns={infoCols} data={[{ gene: "EGFR", score: 0.91 }]} />);

  // The string header "Gene" causes the label to be "About Gene".
  const btn = screen.getByRole("button", { name: /about gene/i });
  expect(btn).toBeInTheDocument();
  expect(btn.getAttribute("data-slot")).toBe("column-info");
});

test("column without meta.info renders no column-info button", () => {
  const plainCols: ColumnDef<InfoRow>[] = [
    { accessorKey: "gene", header: "Gene" },
    { accessorKey: "score", header: "Score" },
  ];
  render(<DataTable columns={plainCols} data={[{ gene: "EGFR", score: 0.91 }]} />);

  expect(document.querySelector("[data-slot='column-info']")).not.toBeInTheDocument();
});

// ── meta.filterable — per-column filter inputs ───────────────────────────────

type FilterRow = { gene: string; score: number };

test("column with meta.filterable renders a labelled filter input", () => {
  const filterCols: ColumnDef<FilterRow>[] = [
    { accessorKey: "gene", header: "Gene", meta: { filterable: true } },
    { accessorKey: "score", header: "Score" },
  ];
  render(
    <DataTable
      columns={filterCols}
      data={[
        { gene: "EGFR", score: 0.9 },
        { gene: "TP53", score: 0.2 },
      ]}
    />,
  );

  expect(screen.getByRole("textbox", { name: /filter gene/i })).toBeInTheDocument();
});

test("typing in the filter input narrows visible rows", async () => {
  const user = userEvent.setup();
  const filterCols: ColumnDef<FilterRow>[] = [
    { accessorKey: "gene", header: "Gene", meta: { filterable: true } },
    { accessorKey: "score", header: "Score" },
  ];
  render(
    <DataTable
      columns={filterCols}
      data={[
        { gene: "EGFR", score: 0.9 },
        { gene: "TP53", score: 0.2 },
        { gene: "BRCA1", score: 0.5 },
      ]}
    />,
  );

  const input = screen.getByRole("textbox", { name: /filter gene/i });
  await user.type(input, "EGFR");

  const rows = screen.getAllByRole("row").filter((r) => !r.closest("thead"));
  expect(rows).toHaveLength(1);
  expect(rows[0]).toHaveTextContent("EGFR");
  expect(screen.queryByText("TP53")).not.toBeInTheDocument();
});

test("table with no filterable column renders no filter row", () => {
  const plainCols: ColumnDef<FilterRow>[] = [
    { accessorKey: "gene", header: "Gene" },
    { accessorKey: "score", header: "Score" },
  ];
  render(
    <DataTable
      columns={plainCols}
      data={[
        { gene: "EGFR", score: 0.9 },
        { gene: "TP53", score: 0.2 },
      ]}
    />,
  );

  // No filter inputs should be present
  expect(screen.queryByRole("textbox", { name: /filter/i })).not.toBeInTheDocument();
  // No filter row data-slot
  expect(document.querySelector('[data-slot="filter-row"]')).not.toBeInTheDocument();
});

// ── meta.className — cell/header class propagation ───────────────────────────

test("meta.className is applied to header <th> cells", () => {
  const numCols: ColumnDef<InfoRow>[] = [
    { accessorKey: "gene", header: "Gene" },
    { accessorKey: "score", header: "Score", meta: { className: "num" } },
  ];
  render(<DataTable columns={numCols} data={[{ gene: "EGFR", score: 0.91 }]} />);

  // The <th> for "Score" should carry the "num" class.
  const ths = screen.getAllByRole("columnheader");
  const scoreTh = ths.find((th) => th.textContent?.includes("Score"));
  expect(scoreTh).toBeDefined();
  expect(scoreTh!.className).toContain("num");
});

test("meta.className is applied to body <td> cells", () => {
  const numCols: ColumnDef<InfoRow>[] = [
    { accessorKey: "gene", header: "Gene" },
    { accessorKey: "score", header: "Score", meta: { className: "num" } },
  ];
  render(<DataTable columns={numCols} data={[{ gene: "EGFR", score: 0.91 }]} />);

  // The <td> containing "0.91" should carry the "num" class.
  const cell = screen.getByText("0.91").closest("td");
  expect(cell).toBeDefined();
  expect(cell!.className).toContain("num");
});

// ── responsive: plain horizontal scroll (sticky-first column reverted) ───────

type ResponsiveRow = { gene: string; mcc: number };
const responsiveColumns: ColumnDef<ResponsiveRow>[] = [
  { accessorKey: "gene", header: "Gene" },
  { accessorKey: "mcc", header: "MCC" },
];
const responsiveData: ResponsiveRow[] = [
  { gene: "CA4", mcc: 2 },
  { gene: "CA12", mcc: 1 },
];

describe("DataTable responsive", () => {
  afterEach(() => cleanup());

  it("scrolls horizontally on narrow screens without freezing a column", () => {
    const { container } = render(<DataTable columns={responsiveColumns} data={responsiveData} />);
    const scroll = container.querySelector("[data-slot='datatable'] .scroll")!;
    expect(scroll.className).toMatch(/overflow-x-auto/);
    // The sticky-first column + right-edge fade were reverted (unreadable on desktop).
    expect(container.querySelector("table")).not.toHaveClass("hf-sticky-first");
    expect(container.querySelector(".hf-scroll-fade")).not.toBeInTheDocument();
  });

  it("does not use the removed block-layout hack", () => {
    const { container } = render(<DataTable columns={responsiveColumns} data={responsiveData} />);
    const scroll = container.querySelector("[data-slot='datatable'] .scroll")!;
    expect(scroll.className).not.toMatch(/\[&_table\]:block/);
    // the real data still renders
    expect(screen.getByText("CA4")).toBeInTheDocument();
  });
});
