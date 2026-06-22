import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { PreRunTrail } from "./PreRunTrail";

afterEach(() => {
  cleanup();
});

describe("PreRunTrail", () => {
  it('marks "Inputs" as the active step (aria-current="step")', () => {
    render(<PreRunTrail />);
    const inputsItem = screen.getByText("Inputs").closest("li");
    expect(inputsItem).toHaveAttribute("aria-current", "step");
  });

  it("shows a stage label for a later step (compound targets / targets)", () => {
    render(<PreRunTrail />);
    // stageLabel(3) = "Compound targets" for the "targets" slug
    expect(screen.getByText(/compound targets/i)).toBeInTheDocument();
  });

  it("does not render any links (non-navigable — no run exists yet)", () => {
    const { container } = render(<PreRunTrail />);
    expect(container.querySelectorAll("a")).toHaveLength(0);
  });

  it('marks non-active items as aria-disabled="true"', () => {
    render(<PreRunTrail />);
    const finalItem = screen.getByText("Final").closest("li");
    expect(finalItem).toHaveAttribute("aria-disabled", "true");
  });
});
