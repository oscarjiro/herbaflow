import { render, screen } from "@testing-library/react";
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
