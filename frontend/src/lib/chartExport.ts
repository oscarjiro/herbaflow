import { saveBlob } from "./download";
import { readChartColors } from "./chartTheme";

/** Theme-independent label colour baked into exported figures (reads on a white page). */
const EXPORT_TEXT = "#000000";

/**
 * Compose an image source onto a canvas and save it as a PNG.
 *
 * This is the single shared compose-to-PNG path used by both the SVG export and
 * the Cytoscape export. It loads `src` into an Image, draws it onto a canvas
 * (with an optional 32 px title strip), fills the background, then toBlob's to
 * PNG and hands the blob to saveBlob — the one canonical save-to-disk path.
 *
 * Dimensions resolve from opts.width/height when given, else the image's natural
 * size, else an 800x400 fallback. A blob: object URL passed as `src` is revoked
 * after drawing; data: URLs (Cytoscape's png() output) need no revoke.
 */
async function composeImageToPng(
  src: string,
  opts: {
    filename: string;
    title?: string;
    background?: string;
    width?: number;
    height?: number;
    transparent?: boolean;
  },
): Promise<void> {
  const colors = readChartColors();
  const bg = opts.background ?? colors.surface ?? colors.bg ?? "#ffffff";

  // Title padding: 32 px strip above the image when a title is requested.
  const titlePad = opts.title ? 32 : 0;

  const isBlobUrl = src.startsWith("blob:");
  const revoke = () => {
    if (isBlobUrl) URL.revokeObjectURL(src);
  };

  return new Promise<void>((resolve, reject) => {
    const img = new Image();

    img.onload = () => {
      try {
        const w = opts.width ?? img.naturalWidth;
        const h = opts.height ?? img.naturalHeight;
        const width = w > 0 ? w : 800;
        const height = h > 0 ? h : 400;

        const dpr = window.devicePixelRatio || 1;
        const canvas = document.createElement("canvas");
        canvas.width = width * dpr;
        canvas.height = (height + titlePad) * dpr;

        const ctx = canvas.getContext("2d");
        if (!ctx) {
          revoke();
          reject(new Error("Canvas 2D context unavailable"));
          return;
        }

        ctx.scale(dpr, dpr);

        // Background fill — skipped for a transparent export so the figure drops
        // onto any page (e.g. a white thesis page) without a coloured backplate.
        if (!opts.transparent) {
          ctx.fillStyle = bg;
          ctx.fillRect(0, 0, width, height + titlePad);
        }

        // Optional title strip. Black on a transparent export (theme-independent,
        // prints legibly on white), else the themed foreground.
        if (opts.title) {
          ctx.fillStyle = opts.transparent ? "#000000" : colors.fg1 || "#000000";
          ctx.font = "600 16px ui-sans-serif, system-ui, sans-serif";
          ctx.textBaseline = "middle";
          ctx.fillText(opts.title, 12, titlePad / 2);
        }

        // Draw the image below the title strip.
        ctx.drawImage(img, 0, titlePad, width, height);

        revoke();

        canvas.toBlob((out) => {
          if (!out) {
            reject(new Error("Canvas export failed"));
            return;
          }
          saveBlob(out, opts.filename);
          resolve();
        }, "image/png");
      } catch (err) {
        revoke();
        reject(err);
      }
    };

    img.onerror = () => {
      revoke();
      reject(new Error("Image load failed"));
    };

    img.src = src;
  });
}

/**
 * Export an SVGSVGElement as a PNG file saved to the user's filesystem.
 *
 * The SVG is serialized to a Blob, then drawn and saved via the shared
 * composeImageToPng helper (with an optional title bar above the chart).
 */
export async function exportSvgAsPng(
  svg: SVGSVGElement,
  opts: { filename: string; title?: string; background?: string },
): Promise<void> {
  // Clone so we don't mutate the live DOM node.
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  // Resolve dimensions: prefer viewBox, then clientWidth/Height, then fallback.
  let w: number;
  let h: number;
  const vb = svg.viewBox?.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    w = vb.width;
    h = vb.height;
  } else if (svg.clientWidth > 0 && svg.clientHeight > 0) {
    w = svg.clientWidth;
    h = svg.clientHeight;
  } else {
    w = 800;
    h = 400;
  }

  // Serialize to a Blob URL.
  const data = new XMLSerializer().serializeToString(clone);
  const svgBlob = new Blob([data], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    await composeImageToPng(svgUrl, { ...opts, width: w, height: h });
  } catch (err) {
    // Preserve the historical SVG-specific failure message.
    if (err instanceof Error && err.message === "Image load failed") {
      throw new Error("SVG image load failed");
    }
    throw err;
  }
}

/**
 * Export a Cytoscape graph as a PNG file saved to the user's filesystem.
 *
 * Renders the full graph to a PNG data URL via cy.png (2x scale, background
 * matching the surface), then draws and saves it through the same
 * composeImageToPng helper so the title strip and save path are shared with the
 * SVG export.
 */
export async function exportCytoscapeAsPng(
  cy: import("cytoscape").Core,
  opts: { filename: string; title?: string },
): Promise<void> {
  // Print-friendly export: black labels with a white halo (legible on a white
  // page, independent of the live theme) on a transparent canvas. The temporary
  // per-node style bypass is removed afterwards so the on-screen graph is intact.
  const nodes = cy.nodes();
  nodes.style({ color: EXPORT_TEXT, "text-outline-color": "#ffffff", "text-outline-width": 2 });
  let dataUrl: string;
  try {
    dataUrl = cy.png({ full: true, scale: 2, bg: "transparent" });
  } finally {
    nodes.removeStyle("color text-outline-color text-outline-width");
  }
  return composeImageToPng(dataUrl, {
    filename: opts.filename,
    title: opts.title,
    transparent: true,
  });
}

/**
 * Export a Plotly graph div as a PNG file. Renders the graph to a PNG data URL
 * via Plotly.toImage (2x scale), then draws + saves it through the same
 * composeImageToPng helper that backs the SVG and Cytoscape exports — one save
 * path, one title strip. Plotly is dynamically imported (cached) so this does
 * not pull Plotly into the main bundle.
 */
export async function exportPlotlyAsPng(
  graphDiv: HTMLElement,
  opts: { filename: string; title?: string },
): Promise<void> {
  const Plotly = (await import("plotly.js-dist-min")).default;
  const rect = graphDiv.getBoundingClientRect();
  const width = rect.width > 0 ? rect.width : 800;
  const height = rect.height > 0 ? rect.height : 420;

  // Render a print-friendly copy: transparent paper/plot and forced black text
  // (theme-independent) so the figure reads on a white page in either theme.
  // Built from the live graph's data + layout without mutating the on-screen chart.
  const gd = graphDiv as HTMLElement & {
    data?: unknown[];
    layout?: {
      font?: { color?: string };
      xaxis?: { tickfont?: { color?: string } };
      yaxis?: { tickfont?: { color?: string } };
      [key: string]: unknown;
    };
  };
  const layout = gd.layout ?? {};
  const printLayout: Record<string, unknown> = {
    ...layout,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { ...(layout.font ?? {}), color: EXPORT_TEXT },
    xaxis: {
      ...(layout.xaxis ?? {}),
      tickfont: { ...(layout.xaxis?.tickfont ?? {}), color: EXPORT_TEXT },
    },
    yaxis: {
      ...(layout.yaxis ?? {}),
      tickfont: { ...(layout.yaxis?.tickfont ?? {}), color: EXPORT_TEXT },
    },
  };
  const dataUrl = await Plotly.toImage(
    { data: gd.data ?? [], layout: printLayout },
    { format: "png", width, height, scale: 2 },
  );
  return composeImageToPng(dataUrl, {
    filename: opts.filename,
    title: opts.title,
    transparent: true,
  });
}
