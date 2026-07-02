import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { HamburgerIcon } from "./HamburgerIcon";

afterEach(() => cleanup());

describe("HamburgerIcon", () => {
  it("reflects the open state on data-state", () => {
    const { container, rerender } = render(<HamburgerIcon open={false} />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("data-state", "closed");
    rerender(<HamburgerIcon open={true} />);
    expect(svg).toHaveAttribute("data-state", "open");
  });
});
