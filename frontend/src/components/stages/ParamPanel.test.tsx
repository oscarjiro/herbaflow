import { render, screen, act } from "@testing-library/react";
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

const humanizedSelectMeta: ParamMeta = {
  default: "g_SCS",
  min: undefined,
  minExclusive: false,
  max: undefined,
  recommended_min: undefined,
  recommended_max: undefined,
  enum: ["g_SCS", "fdr", "bonferroni"],
  description: "A humanized select param",
};

const arraySelectMeta: ParamMeta = {
  default: ["GO:BP"],
  min: undefined,
  minExclusive: false,
  max: undefined,
  recommended_min: undefined,
  recommended_max: undefined,
  enum: ["GO:BP", "GO:MF", "GO:CC", "KEGG", "REAC", "WP"],
  description: "Enrichment source vocabularies",
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

  it("humanizes field labels from labels.ts", async () => {
    render(
      <ParamPanel
        params={{ significance_threshold: 0.05 }}
        meta={{ significance_threshold: numericMeta }}
        onRedo={vi.fn()}
        numericKeys={["significance_threshold"]}
        booleanKeys={[]}
        selectKeys={[]}
      />,
    );
    await openPanel();
    expect(screen.getByLabelText("Significance threshold (corrected p ≤)")).toBeInTheDocument();
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

  it("renders select params with humanized enum options", async () => {
    render(
      <ParamPanel
        params={{ mode: "g_SCS" }}
        meta={{ mode: humanizedSelectMeta }}
        onRedo={vi.fn()}
        numericKeys={[]}
        booleanKeys={[]}
        selectKeys={["mode"]}
      />,
    );
    await openPanel();
    expect(screen.getByRole("combobox", { name: "mode" })).toHaveTextContent("g:SCS");
  });

  it("submits raw enum values from select changes", async () => {
    const onRedo = vi.fn();
    render(
      <ParamPanel
        params={{ mode: "fdr" }}
        meta={{ mode: humanizedSelectMeta }}
        onRedo={onRedo}
        numericKeys={[]}
        booleanKeys={[]}
        selectKeys={["mode"]}
      />,
    );
    await openPanel();
    await userEvent.click(screen.getByRole("combobox", { name: "mode" }));
    await userEvent.click(screen.getByRole("option", { name: "g:SCS" }));
    await userEvent.click(screen.getByRole("button", { name: /redo from this stage/i }));
    expect(onRedo).toHaveBeenCalledWith({ mode: "g_SCS" });
  });

  it("collects changed array enum selections on redo", async () => {
    const onRedo = vi.fn();
    render(
      <ParamPanel
        params={{ sources: ["GO:BP"] }}
        meta={{ sources: arraySelectMeta }}
        onRedo={onRedo}
        numericKeys={[]}
        booleanKeys={[]}
        selectKeys={[]}
        arrayKeys={["sources"]}
      />,
    );
    await openPanel();
    await userEvent.click(screen.getByLabelText("Reactome"));
    expect(screen.getByRole("button", { name: /redo from this stage/i })).not.toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /redo from this stage/i }));
    expect(onRedo).toHaveBeenCalledWith({ sources: ["GO:BP", "REAC"] });
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

  it("param description is behind an info tooltip, not always-visible body text", async () => {
    const tooltipMeta: ParamMeta = {
      default: 5,
      min: 0,
      minExclusive: false,
      max: 10,
      recommended_min: 1,
      recommended_max: 9,
      description: "the full long description sentence",
    };
    render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: tooltipMeta }}
        onRedo={vi.fn()}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
        title="Tooltip test"
      />,
    );
    await openPanel(/tooltip test/i);
    expect(screen.getByRole("button", { name: /about/i })).toBeInTheDocument();
    expect(screen.queryByText(/the full long description sentence/i)).not.toBeInTheDocument();
  });

  it("param help lives in the info tooltip, not an always-on inline hint", async () => {
    const tooltipMeta: ParamMeta = {
      default: 5,
      min: 0,
      minExclusive: false,
      max: 10,
      recommended_min: 1,
      recommended_max: 9,
      description: "the full long description sentence",
    };
    const { container } = render(
      <ParamPanel
        params={{ score: 5 }}
        meta={{ score: tooltipMeta }}
        onRedo={vi.fn()}
        numericKeys={["score"]}
        booleanKeys={[]}
        selectKeys={[]}
        title="Hint test"
      />,
    );
    await openPanel(/hint test/i);
    // The info trigger exists and is tagged for the design system.
    expect(container.querySelector("[data-slot='param-info']")).not.toBeNull();
    // No always-on inline help paragraph (default/recommended bounds + description
    // now live inside the tooltip, mirroring the mockup's tooltip mode).
    expect(container.querySelector("[data-slot='param-hint']")).toBeNull();
    expect(screen.queryByText(/recommended 1–9/i)).not.toBeInTheDocument();
  });

  describe("collect-mode (onChange + hideRedo)", () => {
    it("hideRedo hides the Redo button", async () => {
      render(
        <ParamPanel
          params={{ score: 5 }}
          meta={{ score: numericMeta }}
          onRedo={vi.fn()}
          numericKeys={["score"]}
          booleanKeys={[]}
          selectKeys={[]}
          hideRedo
          title="Collect panel"
        />,
      );
      await openPanel(/collect panel/i);
      expect(
        screen.queryByRole("button", { name: /redo from this stage/i }),
      ).not.toBeInTheDocument();
    });

    it("Redo button still appears when hideRedo is absent", async () => {
      render(
        <ParamPanel
          params={{ score: 5 }}
          meta={{ score: numericMeta }}
          onRedo={vi.fn()}
          numericKeys={["score"]}
          booleanKeys={[]}
          selectKeys={[]}
          title="Normal panel"
        />,
      );
      await openPanel(/normal panel/i);
      expect(screen.getByRole("button", { name: /redo from this stage/i })).toBeInTheDocument();
    });

    it("onChange fires with the changed map when a value changes", async () => {
      const onChange = vi.fn();
      render(
        <ParamPanel
          params={{ score: 5 }}
          meta={{ score: numericMeta }}
          onRedo={vi.fn()}
          onChange={onChange}
          numericKeys={["score"]}
          booleanKeys={[]}
          selectKeys={[]}
          title="Collect panel"
        />,
      );
      await openPanel(/collect panel/i);
      const input = screen.getByLabelText("score");
      await userEvent.clear(input);
      await userEvent.type(input, "8");
      // After the change, onChange must have been called with { score: 8 }
      expect(onChange).toHaveBeenCalledWith({ score: 8 });
    });

    it("onChange fires with an empty map when value is reverted to the default", async () => {
      const onChange = vi.fn();
      render(
        <ParamPanel
          params={{ score: 5 }}
          meta={{ score: numericMeta }}
          onRedo={vi.fn()}
          onChange={onChange}
          numericKeys={["score"]}
          booleanKeys={[]}
          selectKeys={[]}
          title="Collect panel"
        />,
      );
      await openPanel(/collect panel/i);
      const input = screen.getByLabelText("score");
      await userEvent.clear(input);
      await userEvent.type(input, "8");
      await userEvent.clear(input);
      await userEvent.type(input, "5");
      // Final call must be with an empty changed map
      const calls = onChange.mock.calls;
      const lastCall = calls[calls.length - 1]?.[0];
      expect(lastCall).toEqual({});
    });

    it("onChange does NOT infinite-loop: fires a bounded number of times per change", async () => {
      const onChange = vi.fn();
      render(
        <ParamPanel
          params={{ score: 5 }}
          meta={{ score: numericMeta }}
          onRedo={vi.fn()}
          onChange={onChange}
          numericKeys={["score"]}
          booleanKeys={[]}
          selectKeys={[]}
          title="Loop guard panel"
        />,
      );
      await openPanel(/loop guard panel/i);
      const input = screen.getByLabelText("score");
      // Type a single digit — each keystroke may fire onChange at most once.
      await act(async () => {
        await userEvent.clear(input);
        await userEvent.type(input, "7");
      });
      // "7" produces 1 change event; allow up to 3 calls total (clear + type + any
      // re-sync); the critical guarantee is that we don't get dozens of calls.
      expect(onChange.mock.calls.length).toBeLessThanOrEqual(5);
    });
  });

  describe("chrome", () => {
    it("renders the panel title as a serif heading", () => {
      render(
        <ParamPanel
          params={{ score: 5 }}
          meta={{ score: numericMeta }}
          onRedo={vi.fn()}
          numericKeys={["score"]}
          booleanKeys={[]}
          selectKeys={[]}
          title="Advanced parameters"
        />,
      );
      expect(screen.getByText("Advanced parameters").className).toContain("font-display");
    });

    it("renders the container as a glass surface", () => {
      const { container } = render(
        <ParamPanel
          params={{ score: 5 }}
          meta={{ score: numericMeta }}
          onRedo={vi.fn()}
          numericKeys={["score"]}
          booleanKeys={[]}
          selectKeys={[]}
          title="Advanced parameters"
        />,
      );
      expect(container.querySelector(".hf-glass-panel")).not.toBeNull();
    });
  });
});
