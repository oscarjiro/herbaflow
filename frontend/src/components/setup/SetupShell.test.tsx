import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { renderWithRouter } from "../../../tests/renderWithRouter";
import { SetupShell } from "./SetupShell";

afterEach(() => {
  cleanup();
});

describe("SetupShell", () => {
  it("renders children inside the shell", () => {
    renderWithRouter(
      <SetupShell>
        <div data-testid="child">x</div>
      </SetupShell>,
      { withTheme: true },
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("renders the Herbaflow brand link", () => {
    renderWithRouter(
      <SetupShell>
        <div>content</div>
      </SetupShell>,
      { withTheme: true },
    );
    expect(screen.getByText("Herbaflow")).toBeInTheDocument();
  });

  it("renders the pre-run pipeline trail nav", () => {
    renderWithRouter(
      <SetupShell>
        <div>content</div>
      </SetupShell>,
      { withTheme: true },
    );
    expect(screen.getByRole("navigation", { name: /pipeline steps/i })).toBeInTheDocument();
  });
});
