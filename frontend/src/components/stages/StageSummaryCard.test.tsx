import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StageSummaryCard } from "./StageSummaryCard";
import { METRIC_INFO } from "@/lib/metricInfo";

describe("StageSummaryCard", () => {
  it("renders the value and label", () => {
    render(<StageSummaryCard value={42} label="targets" ariaLabel="42 targets" />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("targets")).toBeInTheDocument();
  });

  it("does not render the info affordance when no info is provided", () => {
    render(<StageSummaryCard value={42} label="targets" ariaLabel="42 targets" />);
    expect(document.querySelector("[data-slot='column-info']")).not.toBeInTheDocument();
  });

  it("renders the circle-i affordance labelled from the card label when info is set", () => {
    render(
      <StageSummaryCard
        value={42}
        label="targets"
        ariaLabel="42 targets"
        info={METRIC_INFO.s4.targets}
      />,
    );
    // Reuses the same ColumnInfo primitive as the data-table headers.
    expect(document.querySelector("[data-slot='column-info']")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "About targets" })).toBeInTheDocument();
  });
});
