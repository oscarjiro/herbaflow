import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EditableEntityList } from "./EditableEntityList";

describe("EditableEntityList", () => {
  it("hides user-removed rows", () => {
    render(
      <EditableEntityList
        entities={[
          { id: "a", label: "Alpha", tag: "computed" },
          { id: "b", label: "Beta", tag: "user-removed" },
        ]}
        onRemove={vi.fn()}
        cap={10}
        current={1}
      />,
    );
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByText("Beta")).not.toBeInTheDocument();
  });

  it("disables remove at the one-entity floor", () => {
    render(
      <EditableEntityList
        entities={[{ id: "a", label: "Alpha", tag: "computed" }]}
        onRemove={vi.fn()}
        cap={10}
        current={1}
      />,
    );
    expect(screen.getByRole("button", { name: "Remove Alpha" })).toBeDisabled();
  });
});
