import { render } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { LandingHero } from "./LandingHero";
import { LandingHeroFallback } from "./LandingHeroFallback";

// ---------------------------------------------------------------------------
// matchMedia stub — jsdom has none. Set reduced-motion per test.
// Same shape as BackgroundFX.test.tsx / AiLoader.test.tsx.
// ---------------------------------------------------------------------------
function mockMatchMedia(reducedMotion: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: query.includes("prefers-reduced-motion") ? reducedMotion : false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// jsdom returns null from getContext("webgl") by default, but make the
// no-WebGL branch explicit and deterministic for the relevant tests.
function stubNoWebGl() {
  const original = HTMLCanvasElement.prototype.getContext;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => null);
  return () => {
    HTMLCanvasElement.prototype.getContext = original;
  };
}

beforeEach(() => {
  mockMatchMedia(false);
  document.documentElement.classList.remove("dark");
});

// ---------------------------------------------------------------------------
// 1. Root accessibility / non-interactive contract
// ---------------------------------------------------------------------------
describe("LandingHero — layer contract", () => {
  it("root layer is aria-hidden", () => {
    const restore = stubNoWebGl();
    const { container } = render(<LandingHero />);
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
    restore();
  });

  it("root layer has pointer-events:none", () => {
    const restore = stubNoWebGl();
    const { container } = render(<LandingHero />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.style.pointerEvents).toBe("none");
    restore();
  });

  it("unmount does not throw (lifecycle cleanup guard)", () => {
    const restore = stubNoWebGl();
    const { unmount } = render(<LandingHero />);
    expect(() => unmount()).not.toThrow();
    restore();
  });
});

// ---------------------------------------------------------------------------
// 2. Static fallback branches
// ---------------------------------------------------------------------------
describe("LandingHero — static fallback", () => {
  it("renders the static fallback when WebGL is unavailable", () => {
    const restore = stubNoWebGl();
    const { container } = render(<LandingHero />);
    expect(container.querySelector("[data-landing-hero='fallback']")).toBeTruthy();
    restore();
  });

  it("renders the static fallback under prefers-reduced-motion", () => {
    mockMatchMedia(true);
    const { container } = render(<LandingHero />);
    expect(container.querySelector("[data-landing-hero='fallback']")).toBeTruthy();
  });

  it("does NOT mount the live renderer container in the fallback branch", () => {
    const restore = stubNoWebGl();
    const { container } = render(<LandingHero />);
    expect(container.querySelector("[data-landing-hero='stage']")).toBeNull();
    restore();
  });
});

// ---------------------------------------------------------------------------
// 3. LandingHeroFallback — standalone contract
// ---------------------------------------------------------------------------
describe("LandingHeroFallback", () => {
  it("is aria-hidden and pointer-events:none", () => {
    const { container } = render(<LandingHeroFallback />);
    const el = container.querySelector("[data-landing-hero='fallback']") as HTMLElement;
    expect(el).toBeTruthy();
    expect(el.getAttribute("aria-hidden")).toBe("true");
    expect(el.style.pointerEvents).toBe("none");
  });
});

// ---------------------------------------------------------------------------
// 4. three.js is NOT statically imported by the shell.
// The component module must only pull three via a dynamic import() inside an
// effect (in useAsciiDna), never a top-level `from "three"`. Assert against
// the actual source text so a regression that re-adds a static import fails.
// ---------------------------------------------------------------------------
describe("LandingHero — three.js code-split guard", () => {
  function readSource(relUrl: string): string {
    return readFileSync(fileURLToPath(new URL(relUrl, import.meta.url)), "utf8");
  }

  it("LandingHero source has no top-level static three import", () => {
    const src = readSource("./LandingHero.tsx");
    expect(src).not.toMatch(/^\s*import[^;]*from\s+["']three/m);
  });

  it("useAsciiDna source has no top-level static three import", () => {
    const src = readSource("./useAsciiDna.ts");
    expect(src).not.toMatch(/^\s*import[^;]*from\s+["']three/m);
  });

  it("useAsciiDna loads three only via dynamic import()", () => {
    const src = readSource("./useAsciiDna.ts");
    expect(src).toMatch(/import\(\s*["']three["']\s*\)/);
  });
});
