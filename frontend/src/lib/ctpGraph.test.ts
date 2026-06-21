import { describe, it, expect } from "vitest";
import { buildCtpStylesheet, ctpConcentricLayout } from "./ctpGraph";
import type { ChartColors } from "./chartTheme";

// ---------------------------------------------------------------------------
// Fixture: a complete ChartColors object (same shape as chartTheme.test.ts)
// ---------------------------------------------------------------------------
const COLORS: ChartColors = {
  sage: "#6b7f5e",
  sageDeep: "#445138",
  sageSoft: "#cdd6c2",
  sageFaint: "#eef1e9",
  terracotta: "#b3613f",
  terracottaSoft: "#e6c7b8",
  fg1: "#1b1b17",
  fg2: "#3a3a32",
  fg3: "#6b6b5e",
  border: "#d8d8cf",
  surface: "#fbfaf6",
  bg: "#ffffff",
  success: "#3f7d4f",
  warning: "#b08400",
  danger: "#a23b2d",
  info: "#3a6ea5",
};

describe("ctpConcentricLayout", () => {
  it("uses a concentric (not fcose) layout ranked by node type", () => {
    const layout = ctpConcentricLayout();
    expect(layout.name).toBe("concentric");
  });

  it("places targets at the core (rank 3), compounds at 2, pathways/diseases at 1", () => {
    const layout = ctpConcentricLayout();
    // The concentric callback takes a node with a .data() method
    const makeNode = (type: string) => ({ data: (key: string) => (key === "type" ? type : "") });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const concentric = (layout as any).concentric as (n: unknown) => number;
    expect(concentric(makeNode("target"))).toBe(3);
    expect(concentric(makeNode("compound"))).toBe(2);
    expect(concentric(makeNode("pathway"))).toBe(1);
    expect(concentric(makeNode("disease"))).toBe(1);
    expect(concentric(makeNode("unknown"))).toBe(0);
  });

  it("has animate: false and minNodeSpacing: 28", () => {
    const layout = ctpConcentricLayout();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const l = layout as any;
    expect(l.animate).toBe(false);
    expect(l.minNodeSpacing).toBe(28);
  });
});

describe("buildCtpStylesheet", () => {
  it("color-codes compound nodes with warning color and round-rectangle shape", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    const compoundRule = ss.find((s) => s.selector.includes('type = "compound"'));
    expect(compoundRule).toBeDefined();
    expect(compoundRule?.style["background-color"]).toBe(COLORS.warning);
    expect(compoundRule?.style["shape"]).toBe("round-rectangle");
  });

  it("color-codes target nodes with info color and ellipse shape", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    const targetRule = ss.find(
      (s) => s.selector.includes('type = "target"') && !s.selector.includes("hub"),
    );
    expect(targetRule).toBeDefined();
    expect(targetRule?.style["background-color"]).toBe(COLORS.info);
    expect(targetRule?.style["shape"]).toBe("ellipse");
  });

  it("emphasises hub targets with sageDeep color and larger size", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    expect(ss.some((s) => s.selector.includes('[hub = "true"]'))).toBe(true);
    const hubRule = ss.find((s) => s.selector.includes('[hub = "true"]'));
    expect(hubRule?.style["background-color"]).toBe(COLORS.sageDeep);
    expect(Number(hubRule?.style["width"])).toBeGreaterThan(20);
  });

  it("includes a disease selector with danger color", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    expect(ss.some((s) => s.selector.includes('type = "disease"'))).toBe(true);
    const diseaseRule = ss.find((s) => s.selector.includes('type = "disease"'));
    expect(diseaseRule?.style["background-color"]).toBe(COLORS.danger);
  });

  it("includes a pathway selector with danger color and round-rectangle shape", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    const pathwayRule = ss.find((s) => s.selector.includes('type = "pathway"'));
    expect(pathwayRule).toBeDefined();
    expect(pathwayRule?.style["background-color"]).toBe(COLORS.danger);
    expect(pathwayRule?.style["shape"]).toBe("round-rectangle");
  });

  it("adds directed triangle arrows to edges", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    const edgeRule = ss.find((s) => s.selector === "edge");
    expect(edgeRule?.style["target-arrow-shape"]).toBe("triangle");
    expect(edgeRule?.style["curve-style"]).toBe("bezier");
  });

  it("gives node labels a surface-coloured halo so they stay legible in any theme", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    const base = ss.find((s) => s.selector === "node");
    expect(base?.style["text-outline-color"]).toBe(COLORS.surface);
    expect(Number(base?.style["text-outline-width"])).toBeGreaterThan(0);
  });

  it("uses no raw hex — all colors come from the COLORS fixture (resolved tokens)", () => {
    const ss = buildCtpStylesheet(COLORS) as Array<{
      selector: string;
      style: Record<string, unknown>;
    }>;
    // All background-color values in node rules must be one of the resolved COLORS values
    const tokenValues = new Set(Object.values(COLORS));
    const bgColors = ss
      .filter((s) => !s.selector.startsWith("edge"))
      .map((s) => s.style["background-color"])
      .filter(Boolean);
    for (const v of bgColors) {
      expect(tokenValues.has(v as string)).toBe(true);
    }
  });
});
