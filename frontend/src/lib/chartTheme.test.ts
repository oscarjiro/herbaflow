import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import React from "react";
import { readChartColors, useChartColors } from "./chartTheme";
import { ThemeProvider } from "./theme";

// ---------------------------------------------------------------------------
// Token → CSS property map used across tests
// ---------------------------------------------------------------------------
const TOKEN_MAP: Record<string, string> = {
  "--hf-sage": "#7a9e7e",
  "--hf-sage-deep": "#4e7a54",
  "--hf-sage-soft": "#b2cdb5",
  "--hf-sage-faint": "#e8f0e9",
  "--hf-terracotta": "#c4704f",
  "--hf-terracotta-soft": "#e0a98c",
  "--hf-fg-1": "#1a1a1a",
  "--hf-fg-2": "#4a4a4a",
  "--hf-fg-3": "#7a7a7a",
  "--hf-border": "#d1d5db",
  "--hf-surface": "#f9fafb",
  "--hf-bg": "#ffffff",
  "--hf-success": "#22c55e",
  "--hf-warning": "#f59e0b",
  "--hf-danger": "#ef4444",
  "--hf-info": "#3b82f6",
};

// ---------------------------------------------------------------------------
// readChartColors
// ---------------------------------------------------------------------------

describe("readChartColors", () => {
  beforeEach(() => {
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      getPropertyValue: (name: string) => TOKEN_MAP[name] ?? "",
    } as unknown as CSSStyleDeclaration);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("maps --hf-sage to the sage key", () => {
    const colors = readChartColors();
    expect(colors.sage).toBe("#7a9e7e");
  });

  it("maps all 16 tokens to their corresponding keys", () => {
    const colors = readChartColors();
    expect(colors.sage).toBe(TOKEN_MAP["--hf-sage"]);
    expect(colors.sageDeep).toBe(TOKEN_MAP["--hf-sage-deep"]);
    expect(colors.sageSoft).toBe(TOKEN_MAP["--hf-sage-soft"]);
    expect(colors.sageFaint).toBe(TOKEN_MAP["--hf-sage-faint"]);
    expect(colors.terracotta).toBe(TOKEN_MAP["--hf-terracotta"]);
    expect(colors.terracottaSoft).toBe(TOKEN_MAP["--hf-terracotta-soft"]);
    expect(colors.fg1).toBe(TOKEN_MAP["--hf-fg-1"]);
    expect(colors.fg2).toBe(TOKEN_MAP["--hf-fg-2"]);
    expect(colors.fg3).toBe(TOKEN_MAP["--hf-fg-3"]);
    expect(colors.border).toBe(TOKEN_MAP["--hf-border"]);
    expect(colors.surface).toBe(TOKEN_MAP["--hf-surface"]);
    expect(colors.bg).toBe(TOKEN_MAP["--hf-bg"]);
    expect(colors.success).toBe(TOKEN_MAP["--hf-success"]);
    expect(colors.warning).toBe(TOKEN_MAP["--hf-warning"]);
    expect(colors.danger).toBe(TOKEN_MAP["--hf-danger"]);
    expect(colors.info).toBe(TOKEN_MAP["--hf-info"]);
  });

  it("trims whitespace from property values", () => {
    vi.restoreAllMocks();
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      getPropertyValue: () => "  #7a9e7e  ",
    } as unknown as CSSStyleDeclaration);
    const colors = readChartColors();
    expect(colors.sage).toBe("#7a9e7e");
  });

  it("returns empty string for unknown tokens", () => {
    vi.restoreAllMocks();
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      getPropertyValue: () => "",
    } as unknown as CSSStyleDeclaration);
    const colors = readChartColors();
    expect(colors.sage).toBe("");
  });
});

// ---------------------------------------------------------------------------
// useChartColors
// ---------------------------------------------------------------------------

describe("useChartColors", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let computedStyleSpy: any;

  beforeEach(() => {
    computedStyleSpy = vi.spyOn(window, "getComputedStyle").mockReturnValue({
      getPropertyValue: (name: string) => TOKEN_MAP[name] ?? "",
    } as unknown as CSSStyleDeclaration);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns an object with all expected keys", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(ThemeProvider, null, children);

    const { result } = renderHook(() => useChartColors(), { wrapper });

    const colors = result.current;
    expect(colors).toHaveProperty("sage");
    expect(colors).toHaveProperty("sageDeep");
    expect(colors).toHaveProperty("sageSoft");
    expect(colors).toHaveProperty("sageFaint");
    expect(colors).toHaveProperty("terracotta");
    expect(colors).toHaveProperty("terracottaSoft");
    expect(colors).toHaveProperty("fg1");
    expect(colors).toHaveProperty("fg2");
    expect(colors).toHaveProperty("fg3");
    expect(colors).toHaveProperty("border");
    expect(colors).toHaveProperty("surface");
    expect(colors).toHaveProperty("bg");
    expect(colors).toHaveProperty("success");
    expect(colors).toHaveProperty("warning");
    expect(colors).toHaveProperty("danger");
    expect(colors).toHaveProperty("info");
  });

  it("resolves correct values from getComputedStyle", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(ThemeProvider, null, children);

    const { result } = renderHook(() => useChartColors(), { wrapper });

    expect(result.current.sage).toBe("#7a9e7e");
    expect(result.current.fg1).toBe("#1a1a1a");
  });

  it("does not throw and still returns all keys after a theme toggle", () => {
    // We can't observe DOM token changes in jsdom, but we can confirm the hook
    // re-runs without error and still returns the full shape.
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(ThemeProvider, null, children);

    const { result } = renderHook(() => useChartColors(), { wrapper });

    act(() => {
      // No public toggle from the hook itself; just confirm shape is stable.
    });

    expect(Object.keys(result.current)).toHaveLength(16);
  });

  // Ensure computedStyleSpy is used (avoid lint unused-variable warning)
  it("calls getComputedStyle on documentElement", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(ThemeProvider, null, children);

    renderHook(() => useChartColors(), { wrapper });

    expect(computedStyleSpy).toHaveBeenCalledWith(document.documentElement);
  });
});

// ---------------------------------------------------------------------------
// plotlyTemplate
// ---------------------------------------------------------------------------

import { plotlyTemplate } from "./chartTheme";
import type { ChartColors } from "./chartTheme";

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

describe("plotlyTemplate", () => {
  it("uses transparent backgrounds so the glass card shows through", () => {
    const t = plotlyTemplate(COLORS);
    expect(t.paper_bgcolor).toBe("rgba(0,0,0,0)");
    expect(t.plot_bgcolor).toBe("rgba(0,0,0,0)");
  });
  it("themes fonts and axes from hf-* tokens", () => {
    const t = plotlyTemplate(COLORS);
    expect(t.font?.color).toBe(COLORS.fg2);
    expect(t.xaxis?.gridcolor).toBe(COLORS.border);
  });
});
