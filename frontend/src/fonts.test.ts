import { describe, it, expect, beforeAll } from "vitest";

// Importing the module runs its side effect: it preloads the critical faces.
describe("self-hosted fonts", () => {
  beforeAll(async () => {
    await import("./fonts");
  });

  it("preloads the critical font faces as font/woff2 with crossorigin", () => {
    const links = Array.from(
      document.head.querySelectorAll<HTMLLinkElement>("link[rel='preload'][as='font']"),
    );
    // body 400 + display 400
    expect(links.length).toBeGreaterThanOrEqual(2);
    for (const link of links) {
      expect(link.type).toBe("font/woff2");
      expect(link.crossOrigin).toBe("anonymous");
      expect(link.href).toBeTruthy();
    }
  });
});
