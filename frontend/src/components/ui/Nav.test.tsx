import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { renderWithRouter } from "../../../tests/renderWithRouter";
import { Nav } from "./Nav";

afterEach(() => cleanup());

describe("Nav", () => {
  it("renders on non-run routes", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis"], withTheme: true });
    expect(screen.getByRole("link", { name: "Herbaflow" })).toBeInTheDocument();
  });

  it("hides on the run page", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis/run-1"], withTheme: true });
    expect(screen.queryByRole("link", { name: "Herbaflow" })).not.toBeInTheDocument();
  });
});
