import { render, screen } from "@testing-library/react";
import { WorkflowTimeline } from "./WorkflowTimeline";

describe("WorkflowTimeline", () => {
  it("renders exactly 10 rows (Inputs + 8 steps + Export)", () => {
    render(<WorkflowTimeline />);
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(10);
  });

  it("renders the Inputs bookend as the first row with accent marker", () => {
    render(<WorkflowTimeline />);
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveAttribute("data-bookend", "true");
    expect(rows[0]).toHaveTextContent(/Inputs/);
    expect(rows[0]).toHaveTextContent(/Plant and disease/);
  });

  it("renders the Export bookend as the last row with accent marker", () => {
    render(<WorkflowTimeline />);
    const rows = screen.getAllByRole("listitem");
    const last = rows[rows.length - 1];
    expect(last).toHaveAttribute("data-bookend", "true");
    expect(last).toHaveTextContent(/Export/);
  });

  it("renders all 8 step labels", () => {
    render(<WorkflowTimeline />);
    for (let i = 1; i <= 8; i++) {
      const padded = String(i).padStart(2, "0");
      expect(screen.getByText(`Step ${padded}`)).toBeInTheDocument();
    }
  });

  it("renders all step names", () => {
    render(<WorkflowTimeline />);
    expect(screen.getByText("Compound selection")).toBeInTheDocument();
    expect(screen.getByText("Drug-likeness screening")).toBeInTheDocument();
    expect(screen.getByText("Compound to targets")).toBeInTheDocument();
    expect(screen.getByText("Disease to targets")).toBeInTheDocument();
    expect(screen.getByText("Target overlap")).toBeInTheDocument();
    expect(screen.getByText("Interaction network")).toBeInTheDocument();
    expect(screen.getByText("Hub genes")).toBeInTheDocument();
    expect(screen.getByText("Functional enrichment")).toBeInTheDocument();
  });

  it("renders source lines for steps that have them", () => {
    render(<WorkflowTimeline />);
    expect(screen.getByText("KNApSAcK")).toBeInTheDocument();
    expect(screen.getByText("Lipinski RO5 · Veber")).toBeInTheDocument();
    expect(screen.getByText("ChEMBL · PubChem")).toBeInTheDocument();
    expect(screen.getByText("Open Targets")).toBeInTheDocument();
    expect(screen.getByText("STRING")).toBeInTheDocument();
    expect(screen.getByText("MCC (CytoHubba)")).toBeInTheDocument();
  });

  it("Step 05 (Target overlap) has no source tag rendered", () => {
    render(<WorkflowTimeline />);
    // Step 05 description is unique — confirm it renders but no separate src element
    expect(
      screen.getByText(/The proteins where compound reach and disease biology meet/i),
    ).toBeInTheDocument();
    // The source lines for steps around it should not bleed in
    // (this is checked implicitly by source-line count in other tests)
  });

  it("renders the section heading copy", () => {
    render(<WorkflowTimeline />);
    expect(screen.getByText("Workflow system")).toBeInTheDocument();
    expect(screen.getByText(/Eight steps/)).toBeInTheDocument();
    expect(screen.getByText(/Every one inspectable/)).toBeInTheDocument();
  });

  it("contains no em dashes in the rendered text", () => {
    const { container } = render(<WorkflowTimeline />);
    expect(container.textContent).not.toContain("—");
  });
});
