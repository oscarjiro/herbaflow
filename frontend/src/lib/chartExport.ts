import { saveBlob } from "./download";
import { readChartColors } from "./chartTheme";

/**
 * Export an SVGSVGElement as a PNG file saved to the user's filesystem.
 *
 * The SVG is serialized to a Blob, loaded into an Image, drawn onto a canvas
 * (with an optional title bar above the chart), then toBlob'd to PNG and
 * handed to saveBlob — the one canonical save-to-disk path.
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

  const colors = readChartColors();
  const bg = opts.background ?? colors.surface ?? colors.bg ?? "#ffffff";

  // Title padding: 32 px strip above the chart when a title is requested.
  const titlePad = opts.title ? 32 : 0;

  return new Promise<void>((resolve, reject) => {
    const img = new Image();

    img.onload = () => {
      try {
        const dpr = window.devicePixelRatio || 1;
        const canvas = document.createElement("canvas");
        canvas.width = w * dpr;
        canvas.height = (h + titlePad) * dpr;

        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("Canvas 2D context unavailable"));
          return;
        }

        ctx.scale(dpr, dpr);

        // Background fill.
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, w, h + titlePad);

        // Optional title strip.
        if (opts.title) {
          ctx.fillStyle = colors.fg1 || "#000000";
          ctx.font = "600 16px ui-sans-serif, system-ui, sans-serif";
          ctx.textBaseline = "middle";
          ctx.fillText(opts.title, 12, titlePad / 2);
        }

        // Draw the SVG image below the title strip.
        ctx.drawImage(img, 0, titlePad, w, h);

        URL.revokeObjectURL(svgUrl);

        canvas.toBlob((out) => {
          if (!out) {
            reject(new Error("Canvas export failed"));
            return;
          }
          saveBlob(out, opts.filename);
          resolve();
        }, "image/png");
      } catch (err) {
        URL.revokeObjectURL(svgUrl);
        reject(err);
      }
    };

    img.onerror = () => {
      URL.revokeObjectURL(svgUrl);
      reject(new Error("SVG image load failed"));
    };

    img.src = svgUrl;
  });
}
