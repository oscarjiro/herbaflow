import { fireEvent, render, screen } from "@testing-library/react";
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
  expect(screen.getByLabelText(/rows per page/i)).toBeInTheDocument();
});
