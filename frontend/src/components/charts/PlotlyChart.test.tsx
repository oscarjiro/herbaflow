import React from "react";
import { render, screen } from "@testing-library/react";
import { ThemeProvider } from "@/lib/theme";
import { PlotlyChart } from "./PlotlyChart";

// Mock the lazy plotly factory: capture props passed to <Plot/>.
const seen: { config?: Record<string, unknown>; data?: unknown } = {};
vi.mock("react-plotly.js/factory", () => ({
  default: () => (props: { config?: Record<string, unknown>; data?: unknown }) => {
    seen.config = props.config;
    seen.data = props.data;
    return <div data-testid="plot" />;
  },
}));
vi.mock("plotly.js-dist-min", () => ({ default: {} }));

function wrap(ui: React.ReactNode) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("PlotlyChart", () => {
  it("renders the plot and removes Plotly's own image-download button", async () => {
    wrap(<PlotlyChart data={[{ type: "bar", x: [1], y: [2] }]} />);
    expect(await screen.findByTestId("plot")).toBeInTheDocument();
    expect(seen.config?.displaylogo).toBe(false);
    expect(seen.config?.modeBarButtonsToRemove).toContain("toImage");
  });
});
