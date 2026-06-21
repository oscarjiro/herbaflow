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

  const Plotly: {
    toImage(graphDiv: HTMLElement, opts?: ToImageOptions): Promise<string>;
    [key: string]: unknown;
  };

  export default Plotly;
}
