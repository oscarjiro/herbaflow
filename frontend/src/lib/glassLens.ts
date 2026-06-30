/**
 * Liquid-glass lens displacement map (one canonical home).
 *
 * Apple-style glass refracts at its rounded EDGES, not as uniform watery noise.
 * This module generates a squircle "surface normal" map: the flat centre stays
 * neutral (no displacement) and the bend ramps up toward the rim along the
 * outward normal. feDisplacementMap (in __root.tsx, filter #hf-liquid) reads
 * R as the x-shift channel and G as the y-shift channel.
 *
 * The pixel math (computeLensRGBA) is pure and unit-tested; buildLensDataUrl
 * wraps it in a canvas and is a no-op ("") under SSR / jsdom (no 2D context),
 * which degrades to clear glass with no refraction rather than throwing.
 */

/** Default bezel width as a fraction of the half-min dimension. */
export const GLASS_LENS_BEZEL = 0.5;

/** Pure RGBA pixel data for a squircle lens normal map (no canvas needed). */
export function computeLensRGBA(w: number, h: number, bezelFrac: number): Uint8ClampedArray {
  const data = new Uint8ClampedArray(w * h * 4);
  const halfW = w / 2;
  const halfH = h / 2;
  const rad = Math.min(halfW, halfH) * 0.55;
  const band = Math.min(halfW, halfH) * bezelFrac;

  // Signed distance to a rounded rectangle (negative inside), centred coords.
  const sd = (px: number, py: number): number => {
    const qx = Math.abs(px) - (halfW - rad);
    const qy = Math.abs(py) - (halfH - rad);
    const ox = Math.max(qx, 0);
    const oy = Math.max(qy, 0);
    return Math.hypot(ox, oy) + Math.min(Math.max(qx, qy), 0) - rad;
  };

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const px = x - halfW + 0.5;
      const py = y - halfH + 0.5;
      const d = sd(px, py);
      let nx = 0;
      let ny = 0;
      let mag = 0;
      if (d < 0 && d > -band) {
        // Outward normal = gradient of the SDF (finite difference).
        const gx = sd(px + 1, py) - sd(px - 1, py);
        const gy = sd(px, py + 1) - sd(px, py - 1);
        const gl = Math.hypot(gx, gy) || 1;
        nx = gx / gl;
        ny = gy / gl;
        const t = (d + band) / band; // 0 at the inner edge of the band, 1 at the rim
        // Bend peaks mid-band and fades to 0 at BOTH the inner edge and the rim,
        // so the displacement never smears the razor-sharp clear-path backdrop
        // into a hard caustic line at the surface edge (the "star" artifact).
        mag = Math.sin(t * Math.PI);
      }
      const i = (y * w + x) * 4;
      // Uint8ClampedArray rounds + clamps to [0,255] on assignment.
      data[i] = 128 + nx * mag * 127;
      data[i + 1] = 128 + ny * mag * 127;
      data[i + 2] = 128;
      data[i + 3] = 255;
    }
  }
  return data;
}

/** Canvas-rendered data-URI of the lens map, or "" under SSR / no 2D context. */
export function buildLensDataUrl(bezelFrac: number = GLASS_LENS_BEZEL): string {
  if (typeof document === "undefined") return "";
  const w = 256;
  const h = 192;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  const img = ctx.createImageData(w, h);
  img.data.set(computeLensRGBA(w, h, bezelFrac));
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL();
}
