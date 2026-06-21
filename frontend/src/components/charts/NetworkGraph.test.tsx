import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "@/lib/theme";

// ---------------------------------------------------------------------------
// Mock react-cytoscapejs so cytoscape never really renders in jsdom. The stub
// invokes the cy callback with a minimal Core and exposes the element count
// via a data attribute so we can assert the caller passed elements through.
// ---------------------------------------------------------------------------
vi.mock("react-cytoscapejs", () => ({
  default: ({ cy, elements }: { cy?: (c: unknown) => void; elements?: unknown[] }) => {
    // Chainable on/off so the tooltip wiring's `cy.off(...).on(...)` runs as it
    // does against the real cytoscape Core.
    const core: Record<string, unknown> = {
      png: () => "data:image/png;base64,AAAA",
      nodes: () => [],
    };
    core.on = () => core;
    core.off = () => core;
    cy?.(core);
    return React.createElement("div", {
      "data-testid": "cytoscape",
      "data-count": String(elements?.length ?? 0),
    });
  },
}));

// Mock the export so clicking Download does not touch canvas/Image.
vi.mock("@/lib/chartExport", () => ({
  exportCytoscapeAsPng: vi.fn().mockResolvedValue(undefined),
}));

import { NetworkGraph } from "./NetworkGraph";
import { exportCytoscapeAsPng } from "@/lib/chartExport";

const ELEMENTS = [
  { data: { id: "A", label: "A" } },
  { data: { id: "B", label: "B" } },
  { data: { id: "e-0", source: "A", target: "B" } },
];

function wrap(ui: React.ReactNode) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("NetworkGraph", () => {
  it("renders the ChartFrame title and Download PNG control", () => {
    wrap(
      <NetworkGraph
        title="Interaction network"
        filename="ppi_network.png"
        elements={ELEMENTS}
        stylesheet={[]}
      />,
    );
    expect(screen.getByText("Interaction network")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
  });

  it("passes the elements through to the cytoscape component", () => {
    wrap(
      <NetworkGraph
        title="Interaction network"
        filename="ppi_network.png"
        elements={ELEMENTS}
        stylesheet={[]}
      />,
    );
    const stub = screen.getByTestId("cytoscape");
    expect(stub.getAttribute("data-count")).toBe("3");
  });

  it("renders the tray content when provided", () => {
    wrap(
      <NetworkGraph
        title="Interaction network"
        filename="ppi_network.png"
        elements={ELEMENTS}
        stylesheet={[]}
        tray={<p>Not connected at this confidence: ABCA1</p>}
      />,
    );
    expect(screen.getByText(/not connected at this confidence: abca1/i)).toBeInTheDocument();
  });

  it("calls exportCytoscapeAsPng on Download click", async () => {
    wrap(
      <NetworkGraph
        title="Interaction network"
        filename="ppi_network.png"
        elements={ELEMENTS}
        stylesheet={[]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /download png/i }));
    expect(exportCytoscapeAsPng).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ title: "Interaction network", filename: "ppi_network.png" }),
    );
  });

  it("renders an optional legend below the graph", () => {
    wrap(
      <NetworkGraph
        title="PPI network"
        filename="ppi.png"
        elements={[]}
        stylesheet={[]}
        legend={<div>Compounds · Targets · Pathways</div>}
      />,
    );
    expect(screen.getByText(/compounds · targets · pathways/i)).toBeInTheDocument();
  });

  it("wires the nodeTooltip handler without throwing", () => {
    expect(() =>
      wrap(
        <NetworkGraph
          title="PPI network"
          filename="ppi.png"
          elements={[]}
          stylesheet={[]}
          nodeTooltip={(data) => String(data["label"] ?? "")}
        />,
      ),
    ).not.toThrow();
  });
});
