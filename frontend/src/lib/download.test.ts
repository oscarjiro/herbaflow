import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchBlobDownload } from "./download";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFetchOk(options: { blob?: Blob; contentDisposition?: string }) {
  const { blob = new Blob(["data"]), contentDisposition } = options;
  const headers = new Headers();
  if (contentDisposition) headers.set("Content-Disposition", contentDisposition);
  return vi.fn().mockResolvedValue({
    ok: true,
    blob: () => Promise.resolve(blob),
    headers,
  });
}

function makeFetchError(status: number, problem: object) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    statusText: "Not Found",
    json: () => Promise.resolve(problem),
    headers: new Headers(),
  });
}

function makeFetchErrorBadJson(status: number, statusText: string) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    statusText,
    json: () => Promise.reject(new SyntaxError("not json")),
    headers: new Headers(),
  });
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let appendSpy: any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let clickSpy: any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let createObjectURLSpy: any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let revokeObjectURLSpy: any;

beforeEach(() => {
  clickSpy = vi.fn();
  appendSpy = vi.spyOn(document.body, "appendChild").mockImplementation((node) => {
    // Intercept click on the appended anchor
    if (node instanceof HTMLAnchorElement) {
      node.click = clickSpy;
    }
    return node;
  });
  vi.spyOn(document.body, "removeChild").mockImplementation((node) => node);
  createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
  revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("fetchBlobDownload — success path", () => {
  it("uses the Content-Disposition quoted filename", async () => {
    globalThis.fetch = makeFetchOk({
      contentDisposition: 'attachment; filename="herbaflow_plant_disease_2026-06-19.zip"',
    });

    await fetchBlobDownload("http://localhost:8000/export/all-results.zip");

    expect(appendSpy).toHaveBeenCalled();
    const anchor = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("herbaflow_plant_disease_2026-06-19.zip");
    expect(anchor.href).toContain("blob:");
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURLSpy).toHaveBeenCalledWith("blob:mock-url");
  });

  it("uses the Content-Disposition unquoted filename", async () => {
    globalThis.fetch = makeFetchOk({
      contentDisposition: "attachment; filename=report.md",
    });

    await fetchBlobDownload("http://localhost:8000/export/report.md");

    const anchor = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("report.md");
  });

  it("falls back to fallbackName when no Content-Disposition header", async () => {
    globalThis.fetch = makeFetchOk({});

    await fetchBlobDownload("http://localhost:8000/export/report.md", "my-fallback.md");

    const anchor = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("my-fallback.md");
  });

  it("falls back to URL last-segment when no header and no fallbackName", async () => {
    globalThis.fetch = makeFetchOk({});

    await fetchBlobDownload("http://localhost:8000/export/all-results.zip");

    const anchor = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("all-results.zip");
  });

  it("creates and revokes the object URL", async () => {
    globalThis.fetch = makeFetchOk({ contentDisposition: 'filename="x.zip"' });

    await fetchBlobDownload("http://localhost:8000/export/x.zip");

    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLSpy).toHaveBeenCalledTimes(1);
  });
});

describe("fetchBlobDownload — error path", () => {
  it("throws the parsed Problem on a 404 response", async () => {
    const problem = { status: 404, title: "Not Found", detail: "Report not found." };
    globalThis.fetch = makeFetchError(404, problem);

    await expect(fetchBlobDownload("http://localhost:8000/export/report.md")).rejects.toEqual(
      problem,
    );
  });

  it("throws a minimal Problem when the body is not JSON", async () => {
    globalThis.fetch = makeFetchErrorBadJson(500, "Internal Server Error");

    await expect(fetchBlobDownload("http://localhost:8000/export/report.md")).rejects.toMatchObject(
      {
        status: 500,
        title: "Internal Server Error",
      },
    );
  });
});
