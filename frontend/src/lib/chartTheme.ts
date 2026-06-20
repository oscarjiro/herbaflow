import { useMemo } from "react";
import { useTheme } from "@/lib/theme";

/**
 * Concrete color values read from the hf-* CSS custom properties.
 *
 * Charts receive these as plain strings (not var(--hf-...)) so that serialized
 * SVG exports carry the correct resolved color values rather than unresolved
 * CSS variable references.
 */
export type ChartColors = {
  sage: string;
  sageDeep: string;
  sageSoft: string;
  sageFaint: string;
  terracotta: string;
  terracottaSoft: string;
  fg1: string;
  fg2: string;
  fg3: string;
  border: string;
  surface: string;
  bg: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
};

/**
 * Read all chart colors from CSS custom properties on the document root.
 * Call inside a hook or an effect — not at module load time — so the DOM is ready.
 */
export function readChartColors(): ChartColors {
  const style = getComputedStyle(document.documentElement);
  const get = (token: string) => style.getPropertyValue(token).trim();
  return {
    sage: get("--hf-sage"),
    sageDeep: get("--hf-sage-deep"),
    sageSoft: get("--hf-sage-soft"),
    sageFaint: get("--hf-sage-faint"),
    terracotta: get("--hf-terracotta"),
    terracottaSoft: get("--hf-terracotta-soft"),
    fg1: get("--hf-fg-1"),
    fg2: get("--hf-fg-2"),
    fg3: get("--hf-fg-3"),
    border: get("--hf-border"),
    surface: get("--hf-surface"),
    bg: get("--hf-bg"),
    success: get("--hf-success"),
    warning: get("--hf-warning"),
    danger: get("--hf-danger"),
    info: get("--hf-info"),
  };
}

/**
 * React hook that returns resolved chart colors, re-memoized whenever the
 * active theme (light/dark) changes so charts stay in sync with the toggle.
 */
export function useChartColors(): ChartColors {
  const { theme } = useTheme();
  return useMemo(() => readChartColors(), [theme]);
}

import type { Layout } from "plotly.js";

/**
 * Plotly layout template themed from resolved hf-* tokens. Transparent
 * backgrounds let the glass ChartFrame show through; fonts/axes/colorway track
 * the editorial palette. Charts merge this under their own data-specific layout.
 */
export function plotlyTemplate(colors: ChartColors): Partial<Layout> {
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: colors.fg2, family: "ui-sans-serif, system-ui, sans-serif", size: 12 },
    colorway: [
      colors.sage,
      colors.terracotta,
      colors.info,
      colors.warning,
      colors.sageDeep,
      colors.success,
    ],
    margin: { l: 8, r: 16, t: 8, b: 40 },
    xaxis: {
      gridcolor: colors.border,
      zerolinecolor: colors.border,
      tickfont: { color: colors.fg3 },
    },
    yaxis: {
      gridcolor: colors.border,
      zerolinecolor: colors.border,
      tickfont: { color: colors.fg2 },
    },
    hoverlabel: {
      bgcolor: colors.surface,
      bordercolor: colors.border,
      font: { color: colors.fg1 },
    },
  };
}
