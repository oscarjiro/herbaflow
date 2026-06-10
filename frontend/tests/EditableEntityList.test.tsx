import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EditableEntityList } from "../src/components/stages/EditableEntityList";

describe("EditableEntityList", () => {
  it("disables remove on the single remaining entity", () => {
    render(
      <EditableEntityList
        entities={[{ id: "a", label: "Only", tag: "computed" }]}
        onRemove={() => {}}
        cap={10}
        current={1}
      />,
    );
    expect(screen.getByRole("button", { name: /remove only/i })).toBeDisabled();
  });

  it("enables remove when more than one entity remains", () => {
    render(
      <EditableEntityList
        entities={[
          { id: "a", label: "One", tag: "computed" },
          { id: "b", label: "Two", tag: "computed" },
        ]}
        onRemove={() => {}}
        cap={10}
        current={2}
      />,
    );
    expect(screen.getByRole("button", { name: /remove one/i })).not.toBeDisabled();
  });
});
