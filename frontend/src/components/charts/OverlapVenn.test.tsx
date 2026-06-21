import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThemeProvider } from "@/lib/theme";
import { OverlapVenn } from "./OverlapVenn";

function wrap(ui: React.ReactNode) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("OverlapVenn", () => {
  // @upsetjs/react renders an area-proportional venn as SVG in jsdom. The set
  // labels and value labels are laid out as <text>/<title> nodes.
  it("renders a two-set venn from the counts", () => {
    const { container } = wrap(
      <OverlapVenn compoundCount={30} diseaseCount={20} overlapCount={8} overlapGenes={["TP53"]} />,
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
    // Both set names appear (@upsetjs renders each name in more than one node:
    // the visible label and a <title>, so match all occurrences).
    expect(screen.getAllByText(/compound targets/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/disease targets/i).length).toBeGreaterThanOrEqual(1);
  });

  it("renders a single root svg element", () => {
    const { container } = wrap(
      <OverlapVenn compoundCount={30} diseaseCount={20} overlapCount={8} />,
    );
    expect(container.querySelectorAll("svg").length).toBe(1);
  });

  it("sizes each circle to its real cardinality (compound 30 / disease 20)", () => {
    // @upsetjs labels each set with its size, e.g. "Compound targets: 30". This
    // proves the synthesized element arrays gave each circle the right area.
    wrap(<OverlapVenn compoundCount={30} diseaseCount={20} overlapCount={8} />);
    expect(
      screen.getAllByText((_, node) => node?.textContent?.includes("Compound targets: 30") ?? false)
        .length,
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText((_, node) => node?.textContent?.includes("Disease targets: 20") ?? false)
        .length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("makes the auto-computed intersection equal the overlap count (8)", () => {
    // The shared synthetic element ids appear in BOTH sets, so the distinct
    // intersection comes out to exactly overlapCount.
    wrap(<OverlapVenn compoundCount={30} diseaseCount={20} overlapCount={8} />);
    expect(
      screen.getAllByText(
        (_, node) =>
          node?.textContent?.includes("(Compound targets ∩ Disease targets): 8") ?? false,
      ).length,
    ).toBeGreaterThanOrEqual(1);
  });

  // Edge cases
  it("renders without throwing when overlapCount is 0 (disjoint sets)", () => {
    expect(() =>
      wrap(<OverlapVenn compoundCount={30} diseaseCount={20} overlapCount={0} />),
    ).not.toThrow();
  });

  it("renders without throwing when a side is empty", () => {
    expect(() =>
      wrap(<OverlapVenn compoundCount={10} diseaseCount={0} overlapCount={0} />),
    ).not.toThrow();
  });

  it("clamps an over-large overlapCount without throwing", () => {
    // overlapCount cannot exceed min(compoundCount, diseaseCount); guard defensively.
    expect(() =>
      wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={99} />),
    ).not.toThrow();
  });
});
