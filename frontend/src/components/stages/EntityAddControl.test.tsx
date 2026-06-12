import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EntityAddControl } from "./EntityAddControl";

describe("EntityAddControl", () => {
  it("shows current / cap and disables children at cap", () => {
    render(
      <EntityAddControl current={3} cap={3}>
        <button>add</button>
      </EntityAddControl>,
    );
    expect(screen.getByText("3 / 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "add" })).toBeDisabled();
  });

  it("leaves children enabled below cap", () => {
    render(
      <EntityAddControl current={1} cap={3}>
        <button>add</button>
      </EntityAddControl>,
    );
    expect(screen.getByRole("button", { name: "add" })).toBeEnabled();
  });
});
