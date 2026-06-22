import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { renderWithRouter } from "../../../tests/renderWithRouter";
import { Nav } from "./Nav";

afterEach(() => cleanup());

describe("Nav", () => {
  it("renders the clustered links + logo and the theme control on non-run routes", () => {
    // Use "/" (home) — "/analysis" now hides the nav in unified shell mode.
    renderWithRouter(<Nav />, { initialEntries: ["/"], withTheme: true });
    expect(screen.getByRole("link", { name: "Herbaflow home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Analysis" })).toHaveAttribute("href", "/analysis");
    expect(screen.getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
    // The animated icon-only theme switcher (the only button in the nav).
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("hides on the setup route in unified shell mode", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis"], withTheme: true });
    expect(screen.queryByRole("link", { name: "Herbaflow home" })).not.toBeInTheDocument();
  });

  it("hides on the run page", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis/run-1"], withTheme: true });
    expect(screen.queryByRole("link", { name: "Herbaflow home" })).not.toBeInTheDocument();
  });

  it("hides on a per-stage run route (fuzzy match)", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis/run-1/compounds"], withTheme: true });
    expect(screen.queryByRole("link", { name: "Herbaflow home" })).not.toBeInTheDocument();
  });
});
