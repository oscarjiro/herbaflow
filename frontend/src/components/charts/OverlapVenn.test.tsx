import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThemeProvider } from "@/lib/theme";
import { OverlapVenn } from "./OverlapVenn";

function wrap(ui: React.ReactNode) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("OverlapVenn", () => {
  it("renders exactly two circles", () => {
    const { container } = wrap(
      <OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={3} />,
    );
    expect(container.querySelectorAll("circle").length).toBe(2);
  });

  it("labels the only-compound region (10 - 3 = 7)", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={3} />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("labels the overlap region (3)", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={3} />);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("labels the only-disease region (8 - 3 = 5)", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={3} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("renders the set-name label for the compound side", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={3} />);
    expect(screen.getByText("Compound targets")).toBeInTheDocument();
  });

  it("renders the set-name label for the disease side", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={3} />);
    expect(screen.getByText("Disease targets")).toBeInTheDocument();
  });

  it("renders a single root svg element", () => {
    const { container } = wrap(
      <OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={3} />,
    );
    expect(container.querySelectorAll("svg").length).toBe(1);
  });

  // Edge cases
  it("renders without throwing when overlapCount is 0 (disjoint sets)", () => {
    expect(() =>
      wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={0} />),
    ).not.toThrow();
  });

  it("shows 0 in the overlap region when disjoint", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows no negative labels when disjoint (only-compound = 10, only-disease = 8)", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={8} overlapCount={0} />);
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    // No negative numbers in the document
    expect(screen.queryByText(/-\d+/)).toBeNull();
  });

  it("renders without throwing when diseaseCount is 0", () => {
    expect(() =>
      wrap(<OverlapVenn compoundCount={10} diseaseCount={0} overlapCount={0} />),
    ).not.toThrow();
  });

  it("shows no negative labels when diseaseCount is 0", () => {
    wrap(<OverlapVenn compoundCount={10} diseaseCount={0} overlapCount={0} />);
    expect(screen.queryByText(/-\d+/)).toBeNull();
  });
});
