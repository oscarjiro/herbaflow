import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EnrichmentDotChart } from "./EnrichmentDotChart";

vi.mock("./PlotlyChart", () => ({
  PlotlyChart: (p: { data: { y: string[] }[] }) => (
    <div data-testid="plot">{p.data[0]?.y?.join("|")}</div>
  ),
}));

const terms = [
  { source: "GO:BP", name: "apoptotic process", p_value: 1e-8, intersection_size: 12 },
  { source: "KEGG", name: "PI3K-Akt signaling", p_value: 1e-6, intersection_size: 9 },
];

describe("EnrichmentDotChart", () => {
  it("renders a tab per present source with humanized labels and switches", async () => {
    const user = userEvent.setup();
    render(<EnrichmentDotChart terms={terms} />);
    expect(screen.getByRole("tab", { name: "Biological Process" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "KEGG Pathway" })).toBeInTheDocument();
    expect(screen.getByTestId("plot").textContent).toContain("apoptotic process");
    await user.click(screen.getByRole("tab", { name: "KEGG Pathway" }));
    expect(screen.getByTestId("plot").textContent).toContain("PI3K-Akt signaling");
  });

  it("renders nothing when terms is empty", () => {
    const { container } = render(<EnrichmentDotChart terms={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
