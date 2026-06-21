/**
 * PlotlyChart — the single home for Plotly figures.
 *
 * Plotly is heavy (~MBs), so the dist + react-plotly factory are loaded behind
 * React.lazy: Plotly ships as its own chunk, never in the main bundle. The
 * themed layout template is merged under the caller's layout; the modebar keeps
 * zoom/pan/reset but drops Plotly's own image download (ChartFrame owns the one
 * Download-PNG control). onGraphDiv hands the graph node up for export.
 */
import { lazy, Suspense, useMemo } from "react";
import type { Data, Layout } from "plotly.js";
import { Skeleton } from "@/components/ui/skeleton";
import { plotlyTemplate, useChartColors } from "@/lib/chartTheme";

const LazyPlot = lazy(async () => {
  const createPlotlyComponent = (await import("react-plotly.js/factory")).default;
  const Plotly = (await import("plotly.js-dist-min")).default;
  return { default: createPlotlyComponent(Plotly) };
});

type PlotlyChartProps = {
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
  /** Captures the graph DOM node so the parent can export it. */
  onGraphDiv?: (gd: HTMLElement | null) => void;
};

export function PlotlyChart({ data, layout, height = 420, onGraphDiv }: PlotlyChartProps) {
  const colors = useChartColors();
  const mergedLayout = useMemo<Partial<Layout>>(() => {
    const template = plotlyTemplate(colors);
    return {
      ...template,
      autosize: true,
      ...layout,
      // Deep-merge the axis + font objects so a caller that sets xaxis/yaxis
      // (e.g. an axis title or automargin) keeps the themed gridcolor /
      // zerolinecolor / tickfont from the template instead of clobbering the
      // whole axis — a shallow spread drops those back to Plotly's default light
      // grid, which reads as a glaring white grid in dark mode.
      font: { ...template.font, ...layout?.font },
      xaxis: { ...template.xaxis, ...layout?.xaxis },
      yaxis: { ...template.yaxis, ...layout?.yaxis },
    };
  }, [colors, layout]);
  return (
    <Suspense fallback={<Skeleton className="w-full" style={{ height }} />}>
      <div style={{ width: "100%", height }}>
        <LazyPlot
          data={data}
          layout={mergedLayout}
          useResizeHandler
          style={{ width: "100%", height: "100%" }}
          config={{ displaylogo: false, modeBarButtonsToRemove: ["toImage"], responsive: true }}
          onInitialized={(_fig: unknown, gd: HTMLElement) => onGraphDiv?.(gd)}
          onUpdate={(_fig: unknown, gd: HTMLElement) => onGraphDiv?.(gd)}
        />
      </div>
    </Suspense>
  );
}
