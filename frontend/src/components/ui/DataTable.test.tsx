import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "./DataTable";

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
  // The rows-per-page control is the Task-7 Select (an accessible combobox).
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
