import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ParamPanel } from "./ParamPanel";
import type { ParamMeta } from "./ParamPanel";

const numericMeta: ParamMeta = {
  default: 5,
  min: 0,
  minExclusive: false,
  max: 10,
  recommended_min: 1,
  recommended_max: 9,
  description: "A numeric param",
};

const booleanMeta: ParamMeta = {
  default: false,
  min: undefined,
  minExclusive: false,
  max: undefined,
  recommended_min: undefined,
  recommended_max: undefined,
  description: "A boolean param",
};

const selectMeta: ParamMeta = {
  default: "a",
  min: undefined,
  minExclusive: false,
  max: undefined,
  recommended_min: undefined,
  recommended_max: undefined,
  enum: ["a", "b", "c"],
  description: "A select param",
};

async function openPanel(name: RegExp = /parameters/i) {
  await userEvent.click(screen.getByRole("button", { name }));
}

describe("ParamPanel", () => {
  it("hides param fields by default and renders them when opened", async () => {
    render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: numericMeta }}
        onRedo={vi.fn()}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
        title="Test params"
      />,
    );
    expect(screen.getByText("Test params")).toBeInTheDocument();
    expect(screen.queryByLabelText("score")).not.toBeInTheDocument();
    await openPanel(/test params/i);
    expect(screen.getByLabelText("score")).toBeInTheDocument();
  });

  it("Redo button is disabled when no value has changed", async () => {
    render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: numericMeta }}
        onRedo={vi.fn()}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
      />,
    );
    await openPanel();
    expect(screen.getByRole("button", { name: /redo from this stage/i })).toBeDisabled();
  });

  it("Redo arms when a numeric value changes from frozen", async () => {
    const onRedo = vi.fn();
    render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: numericMeta }}
        onRedo={onRedo}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
      />,
    );
    await openPanel();
    const input = screen.getByLabelText("score");
    await userEvent.clear(input);
    await userEvent.type(input, "7");
    expect(screen.getByRole("button", { name: /redo from this stage/i })).not.toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /redo from this stage/i }));
    expect(onRedo).toHaveBeenCalledWith({ score: 7 });
  });

  it("hard-bounds violation blocks Redo and shows error message", async () => {
    render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: numericMeta }}
        onRedo={vi.fn()}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
      />,
    );
    await openPanel();
    const input = screen.getByLabelText("score");
    await userEvent.clear(input);
    await userEvent.type(input, "99");
    expect(screen.getByRole("alert")).toHaveTextContent(/exceeds maximum/i);
    expect(screen.getByRole("button", { name: /redo from this stage/i })).toBeDisabled();
  });

  it("renders boolean params as a checkbox", async () => {
    render(
      <ParamPanel
        params={{ flag: false }}
        meta={{ flag: booleanMeta }}
        onRedo={vi.fn()}
        numericKeys={[]}
        booleanKeys={["flag"]}
        selectKeys={[]}
      />,
    );
    await openPanel();
    expect(screen.getByLabelText("flag")).toBeInTheDocument();
  });

  it("renders select params with enum options", async () => {
    render(
      <ParamPanel
        params={{ mode: "a" }}
        meta={{ mode: selectMeta }}
        onRedo={vi.fn()}
        numericKeys={[]}
        booleanKeys={[]}
        selectKeys={["mode"]}
      />,
    );
    await openPanel();
    expect(screen.getByLabelText("mode")).toBeInTheDocument();
  });

  it("toggles fields open and closed", async () => {
    render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: numericMeta }}
        onRedo={vi.fn()}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
        title="Collapsible"
      />,
    );
    const toggle = screen.getByRole("button", { name: /collapsible/i });
    expect(screen.queryByLabelText("score")).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.getByLabelText("score")).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.queryByLabelText("score")).not.toBeInTheDocument();
  });

  it("Redo is disabled when disabled prop is true", async () => {
    render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: numericMeta }}
        onRedo={vi.fn()}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
        disabled
      />,
    );
    await openPanel();
    expect(screen.getByRole("button", { name: /redo from this stage/i })).toBeDisabled();
  });
});
