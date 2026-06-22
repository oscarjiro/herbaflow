import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@/lib/theme";
import { HubBarChart } from "./HubBarChart";

vi.mock("./PlotlyChart", () => ({
  PlotlyChart: (p: { data: { x: number[] }[] }) => (
    <div data-testid="plot">{p.data[0]?.x?.join(",")}</div>
  ),
}));

function wrap(ui: React.ReactNode) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

const hubs = [
  { gene_symbol: "TP53", mcc: 120, degree: 9, betweenness: 0.4, closeness: 0.7, eigenvector: 0.9 },
  { gene_symbol: "AKT1", mcc: 80, degree: 12, betweenness: 0.2, closeness: 0.6, eigenvector: 0.5 },
];

it("defaults to MCC and switches metric on tab click", async () => {
  const user = userEvent.setup();
  wrap(<HubBarChart hubs={hubs} />);
  // MCC ascending-for-plot order: AKT1=80 (lower) first, TP53=120 (higher) last → "80,120"
  expect(screen.getByTestId("plot").textContent).toBe("80,120");
  await user.click(screen.getByRole("tab", { name: "Degree" }));
  // Degree ascending-for-plot order: TP53=9 (lower) first, AKT1=12 (higher) last → "9,12"
  expect(screen.getByTestId("plot").textContent).toBe("9,12");
});

it("renders no Overall/composite tab", () => {
  wrap(<HubBarChart hubs={hubs} />);
  expect(screen.queryByRole("tab", { name: /overall|composite/i })).toBeNull();
});

it("renders without throwing when hubs is empty", () => {
  wrap(<HubBarChart hubs={[]} />);
  // Empty data yields an empty trace, not a crash; the MCC tab is still present.
  expect(screen.getByTestId("plot").textContent).toBe("");
  expect(screen.getByRole("tab", { name: "MCC" })).toBeInTheDocument();
});
