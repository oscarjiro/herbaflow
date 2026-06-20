import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StageRunningSkeleton } from "./StageRunningSkeleton";

describe("StageRunningSkeleton", () => {
  it("renders the step number and label", () => {
    render(<StageRunningSkeleton stage={3} />);
    expect(screen.getByText(/Step 3/)).toBeInTheDocument();
    expect(screen.getByText(/Compound targets/)).toBeInTheDocument();
  });

  it("renders the running suffix", () => {
    render(<StageRunningSkeleton stage={3} />);
    expect(screen.getByText(/running…/)).toBeInTheDocument();
  });

  it("has an accessible label with the stage number", () => {
    render(<StageRunningSkeleton stage={7} />);
    expect(screen.getByRole("region", { name: "Step 7 running" })).toBeInTheDocument();
  });

  it("renders for stage 1 with correct label", () => {
    render(<StageRunningSkeleton stage={1} />);
    expect(screen.getByText(/Compounds/)).toBeInTheDocument();
  });
});
