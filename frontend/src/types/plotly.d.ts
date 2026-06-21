/**
 * Minimal ambient types for plotly.js-dist-min.
 *
 * The package ships a minified bundle with no bundled .d.ts and there is no
 * @types/plotly.js-dist-min package on npm. We declare only the surface that
 * exportPlotlyAsPng uses: Plotly.toImage.
 */
declare module "plotly.js-dist-min" {
  interface ToImageOptions {
    format?: "png" | "svg" | "jpeg" | "webp";
    width?: number;
    height?: number;
    scale?: number;
  }

  // toImage accepts either a live graph div or a plain figure object
  // ({ data, layout }); the export uses the latter to render a print-friendly
  // copy without mutating the on-screen chart.
  interface ToImageFigure {
    data: unknown[];
    layout?: Record<string, unknown>;
  }

  const Plotly: {
    toImage(graphDiv: HTMLElement | ToImageFigure, opts?: ToImageOptions): Promise<string>;
    [key: string]: unknown;
  };

  export default Plotly;
}
