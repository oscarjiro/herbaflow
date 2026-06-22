import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { renderWithRouter } from "../../../tests/renderWithRouter";
import { Footer } from "./Footer";

afterEach(() => cleanup());

describe("Footer", () => {
  it("renders the blurb and the copyright line, with no link columns", () => {
    renderWithRouter(<Footer />, { initialEntries: ["/"], withTheme: true });
    expect(screen.getByText(/A solo thesis project in computational biology/i)).toBeInTheDocument();
    expect(screen.getByText(/© 2026 · Herbaflow · Oscar Jiro/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows on the setup route (setup lives in the global layout)", () => {
    renderWithRouter(<Footer />, { initialEntries: ["/analysis"], withTheme: true });
    expect(screen.getByText(/© 2026 · Herbaflow · Oscar Jiro/)).toBeInTheDocument();
  });

  it("hides on the run page", () => {
    renderWithRouter(<Footer />, { initialEntries: ["/analysis/run-1"], withTheme: true });
    expect(screen.queryByText(/Oscar Jiro/)).not.toBeInTheDocument();
  });

  it("hides on a per-stage run route (fuzzy match)", () => {
    renderWithRouter(<Footer />, {
      initialEntries: ["/analysis/run-1/compounds"],
      withTheme: true,
    });
    expect(screen.queryByText(/Oscar Jiro/)).not.toBeInTheDocument();
  });
});
