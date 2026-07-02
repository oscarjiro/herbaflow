import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { renderWithRouter } from "../../../tests/renderWithRouter";
import { Nav } from "./Nav";

afterEach(() => cleanup());

describe("Nav", () => {
  it("renders the clustered links + logo and the desktop theme control", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/"], withTheme: true });
    expect(screen.getByRole("link", { name: "Herbaflow home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Analysis" })).toHaveAttribute("href", "/analysis");
    expect(screen.getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
    expect(screen.getByRole("button", { name: /theme: system/i })).toBeInTheDocument();
  });

  it("shows on the setup route (setup lives in the global layout)", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis"], withTheme: true });
    expect(screen.getByRole("link", { name: "Herbaflow home" })).toBeInTheDocument();
  });

  it("hides on the run page", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis/run-1"], withTheme: true });
    expect(screen.queryByRole("link", { name: "Herbaflow home" })).not.toBeInTheDocument();
  });

  it("hides on a per-stage run route (fuzzy match)", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/analysis/run-1/compounds"], withTheme: true });
    expect(screen.queryByRole("link", { name: "Herbaflow home" })).not.toBeInTheDocument();
  });

  it("opens the blurred overlay from the burger trigger", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/"], withTheme: true });
    fireEvent.click(screen.getByRole("button", { name: /open navigation menu/i }));
    const menu = screen.getByRole("dialog", { name: /navigation/i });
    expect(menu).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Analysis" }).at(-1)).toHaveAttribute(
      "href",
      "/analysis",
    );
  });

  it("closes the overlay when an overlay link is clicked", () => {
    renderWithRouter(<Nav />, { initialEntries: ["/"], withTheme: true });
    fireEvent.click(screen.getByRole("button", { name: /open navigation menu/i }));
    fireEvent.click(screen.getAllByRole("link", { name: "About" }).at(-1)!);
    expect(screen.queryByRole("dialog", { name: /navigation/i })).not.toBeInTheDocument();
  });
});
