import { afterEach, describe, expect, it } from "vitest";
import { GLASS_LENS_BEZEL, buildLensDataUrl, computeLensRGBA } from "./glassLens";

describe("computeLensRGBA", () => {
  it("leaves the flat centre undisplaced (neutral 128,128,128,255)", () => {
    const w = 64;
    const h = 64;
    const data = computeLensRGBA(w, h, GLASS_LENS_BEZEL);
    const cx = Math.floor(w / 2);
    const cy = Math.floor(h / 2);
    const i = (cy * w + cx) * 4;
    expect(data[i]).toBe(128);
    expect(data[i + 1]).toBe(128);
    expect(data[i + 2]).toBe(128);
    expect(data[i + 3]).toBe(255);
  });

  it("displaces a pixel inside the rim bezel (channel != 128)", () => {
    const w = 64;
    const h = 64;
    const data = computeLensRGBA(w, h, GLASS_LENS_BEZEL);
    // A pixel near the right edge, vertically centred, sits in the bezel band.
    const x = w - 3;
    const y = Math.floor(h / 2);
    const i = (y * w + x) * 4;
    expect(data[i] !== 128 || data[i + 1] !== 128).toBe(true);
    expect(data[i + 3]).toBe(255);
  });
});

describe("buildLensDataUrl", () => {
  afterEach(() => {
    // restore document if a test deleted it
  });

  it("returns '' under jsdom (no 2D canvas context)", () => {
    // jsdom has no canvas backend, so getContext('2d') is null → guarded to "".
    expect(buildLensDataUrl()).toBe("");
  });

  it("does not throw when document is undefined (SSR)", () => {
    const realDoc = globalThis.document;
    // @ts-expect-error — simulate SSR where document is undefined
    delete globalThis.document;
    expect(() => buildLensDataUrl()).not.toThrow();
    expect(buildLensDataUrl()).toBe("");
    globalThis.document = realDoc;
  });
});
