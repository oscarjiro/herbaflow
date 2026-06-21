import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GLASS_REFRACT_ATTR, applyGlassSupport, detectRefractionSupport } from "./glassSupport";

// glassSupport gates the Chromium-only refraction path. The SAFE DEFAULT is
// frosted: detection must only opt IN to refraction when it can positively
// confirm a Chromium engine with backdrop-filter support. Anything it cannot
// confirm (Safari, Firefox, SSR, missing APIs) stays frosted.

const CHROME_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const SAFARI_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15";
const FIREFOX_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0";

type NavLike = {
  userAgent?: string;
  userAgentData?: { brands: { brand: string; version: string }[] };
};

function stubEnv(opts: {
  nav?: NavLike;
  cssSupports?: (property: string, value: string) => boolean;
}) {
  if (opts.nav !== undefined) {
    vi.stubGlobal("navigator", opts.nav);
  }
  const css = opts.cssSupports ?? (() => true);
  vi.stubGlobal("CSS", { supports: css });
}

describe("detectRefractionSupport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns true for a Chromium engine that supports backdrop-filter (userAgentData)", () => {
    stubEnv({
      nav: { userAgentData: { brands: [{ brand: "Chromium", version: "126" }] } },
      cssSupports: (prop) => prop === "backdrop-filter",
    });
    expect(detectRefractionSupport()).toBe(true);
  });

  it("returns true for Chromium detected via userAgent fallback", () => {
    stubEnv({ nav: { userAgent: CHROME_UA }, cssSupports: () => true });
    expect(detectRefractionSupport()).toBe(true);
  });

  it("returns false (frosted) for Safari — not Chromium", () => {
    stubEnv({ nav: { userAgent: SAFARI_UA }, cssSupports: () => true });
    expect(detectRefractionSupport()).toBe(false);
  });

  it("returns false (frosted) for Firefox — not Chromium", () => {
    stubEnv({ nav: { userAgent: FIREFOX_UA }, cssSupports: () => true });
    expect(detectRefractionSupport()).toBe(false);
  });

  it("returns false when backdrop-filter is unsupported even on Chromium", () => {
    stubEnv({
      nav: { userAgentData: { brands: [{ brand: "Chromium", version: "126" }] } },
      cssSupports: () => false,
    });
    expect(detectRefractionSupport()).toBe(false);
  });

  it("returns false (safe default) when CSS.supports is missing", () => {
    vi.stubGlobal("navigator", { userAgent: CHROME_UA });
    vi.stubGlobal("CSS", undefined);
    expect(detectRefractionSupport()).toBe(false);
  });

  it("returns false (safe default) when navigator is absent / SSR", () => {
    vi.stubGlobal("navigator", undefined);
    vi.stubGlobal("CSS", { supports: () => true });
    expect(detectRefractionSupport()).toBe(false);
  });
});

describe("applyGlassSupport", () => {
  beforeEach(() => {
    document.documentElement.removeAttribute(GLASS_REFRACT_ATTR);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.removeAttribute(GLASS_REFRACT_ATTR);
  });

  it("sets the refraction attribute on <html> for Chromium", () => {
    stubEnv({ nav: { userAgent: CHROME_UA }, cssSupports: () => true });
    applyGlassSupport();
    expect(document.documentElement.getAttribute(GLASS_REFRACT_ATTR)).toBe("on");
  });

  it("leaves <html> without the attribute (frosted default) for Safari", () => {
    stubEnv({ nav: { userAgent: SAFARI_UA }, cssSupports: () => true });
    applyGlassSupport();
    expect(document.documentElement.hasAttribute(GLASS_REFRACT_ATTR)).toBe(false);
  });

  it("removes a stale attribute when detection no longer confirms refraction", () => {
    document.documentElement.setAttribute(GLASS_REFRACT_ATTR, "on");
    stubEnv({ nav: { userAgent: FIREFOX_UA }, cssSupports: () => true });
    applyGlassSupport();
    expect(document.documentElement.hasAttribute(GLASS_REFRACT_ATTR)).toBe(false);
  });

  it("is a no-op without a document (SSR guard) and does not throw", () => {
    const realDoc = globalThis.document;
    // @ts-expect-error — simulate SSR where document is undefined
    delete globalThis.document;
    expect(() => applyGlassSupport()).not.toThrow();
    globalThis.document = realDoc;
  });
});
