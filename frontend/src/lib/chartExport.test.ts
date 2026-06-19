import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as downloadModule from "./download";

// ---------------------------------------------------------------------------
// Fake canvas context
// ---------------------------------------------------------------------------
const fakeCtx = {
  scale: vi.fn(),
  fillRect: vi.fn(),
  fillText: vi.fn(),
  drawImage: vi.fn(),
  fillStyle: "",
  font: "",
  textBaseline: "",
};

// ---------------------------------------------------------------------------
// Fake Image that fires onload synchronously via queueMicrotask
// ---------------------------------------------------------------------------
class FakeImage {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private _src = "";
  set src(v: string) {
    this._src = v;
    queueMicrotask(() => this.onload?.());
  }
  get src() {
    return this._src;
  }
}

class FakeImageError {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private _src = "";
  set src(v: string) {
    this._src = v;
    queueMicrotask(() => this.onerror?.());
  }
  get src() {
    return this._src;
  }
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------
beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    fakeCtx as unknown as CanvasRenderingContext2D,
  );
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((cb) => {
    cb(new Blob(["x"], { type: "image/png" }));
  });
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-svg-url");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.stubGlobal("Image", FakeImage);

  // Reset call counts between tests
  fakeCtx.scale.mockClear();
  fakeCtx.fillRect.mockClear();
  fakeCtx.fillText.mockClear();
  fakeCtx.drawImage.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function makeSvg(width = 400, height = 200): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  return svg;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("exportSvgAsPng — success path", () => {
  it("resolves without throwing for a standard svg", async () => {
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await expect(exportSvgAsPng(svg, { filename: "x.png" })).resolves.toBeUndefined();
  });

  it("calls drawImage on the canvas context", async () => {
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await exportSvgAsPng(svg, { filename: "x.png" });
    expect(fakeCtx.drawImage).toHaveBeenCalledTimes(1);
  });

  it("calls toBlob and calls saveBlob (via URL.createObjectURL side-effect)", async () => {
    const saveBlobSpy = vi.spyOn(downloadModule, "saveBlob");
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await exportSvgAsPng(svg, { filename: "chart.png" });
    // toBlob was called
    expect(HTMLCanvasElement.prototype.toBlob).toHaveBeenCalled();
    // saveBlob was called with the produced blob and filename
    expect(saveBlobSpy).toHaveBeenCalledWith(expect.any(Blob), "chart.png");
  });

  it("renders the title via fillText when title is provided", async () => {
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await exportSvgAsPng(svg, { filename: "hub.png", title: "Hub genes by MCC" });
    expect(fakeCtx.fillText).toHaveBeenCalledWith("Hub genes by MCC", 12, 16);
  });

  it("does not call fillText when no title is provided", async () => {
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await exportSvgAsPng(svg, { filename: "hub.png" });
    expect(fakeCtx.fillText).not.toHaveBeenCalled();
  });

  it("calls URL.revokeObjectURL on success", async () => {
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await exportSvgAsPng(svg, { filename: "x.png" });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-svg-url");
  });

  it("falls back to 800x400 when viewBox is zero and clientWidth/Height are zero", async () => {
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    // No viewBox, no clientWidth/clientHeight (jsdom returns 0)
    await exportSvgAsPng(svg, { filename: "fallback.png" });
    // fillRect called with fallback dimensions
    expect(fakeCtx.fillRect).toHaveBeenCalledWith(0, 0, 800, 400);
  });
});

describe("exportSvgAsPng — error path", () => {
  it("rejects when Image fires onerror", async () => {
    vi.stubGlobal("Image", FakeImageError);
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await expect(exportSvgAsPng(svg, { filename: "x.png" })).rejects.toThrow(
      "SVG image load failed",
    );
  });

  it("calls URL.revokeObjectURL even when Image fires onerror", async () => {
    vi.stubGlobal("Image", FakeImageError);
    const { exportSvgAsPng } = await import("./chartExport");
    const svg = makeSvg(400, 200);
    await exportSvgAsPng(svg, { filename: "x.png" }).catch(() => {});
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-svg-url");
  });
});
