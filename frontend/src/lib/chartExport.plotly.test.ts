import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("plotly.js-dist-min", () => ({
  default: { toImage: vi.fn(async () => "data:image/png;base64,AAAA") },
}));
vi.mock("./download", () => ({ saveBlob: vi.fn() }));

import { exportPlotlyAsPng } from "./chartExport";

// ---------------------------------------------------------------------------
// Minimal jsdom environment stubs so composeImageToPng can complete.
// (FakeImage fires onload synchronously so the promise resolves in tests.)
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

const fakeCtx = {
  scale: vi.fn(),
  fillRect: vi.fn(),
  fillText: vi.fn(),
  drawImage: vi.fn(),
  fillStyle: "",
  font: "",
  textBaseline: "",
};

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    fakeCtx as unknown as CanvasRenderingContext2D,
  );
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((cb) => {
    cb(new Blob(["x"], { type: "image/png" }));
  });
  vi.stubGlobal("Image", FakeImage);
  fakeCtx.scale.mockClear();
  fakeCtx.fillRect.mockClear();
  fakeCtx.fillText.mockClear();
  fakeCtx.drawImage.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("exportPlotlyAsPng", () => {
  it("renders a transparent, dark-text figure to a PNG and saves it", async () => {
    const Plotly = (await import("plotly.js-dist-min")).default;
    const gd = document.createElement("div");
    // jsdom has no canvas image decode; assert toImage gets a print-friendly figure.
    await exportPlotlyAsPng(gd, { filename: "x.png", title: "X" });
    expect(Plotly.toImage).toHaveBeenCalledWith(
      expect.objectContaining({
        layout: expect.objectContaining({
          paper_bgcolor: "rgba(0,0,0,0)",
          font: expect.objectContaining({ color: "#000000" }),
        }),
      }),
      expect.objectContaining({ format: "png" }),
    );
    // Transparent export must not paint a background rectangle.
    expect(fakeCtx.fillRect).not.toHaveBeenCalled();
  });
});
