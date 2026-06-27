import { render, act } from "@testing-library/react";
import { vi } from "vitest";
import { BackgroundFX, parseCssColor, flowPaletteFromTokens } from "./BackgroundFX";
import { GRAIN_ENABLED } from "@/lib/grain";

// ---------------------------------------------------------------------------
// matchMedia stub — jsdom has none. Set reduced-motion per test.
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

// We cannot easily spy on native `import()`. Instead we verify the flow
// container is absent when glow !== "flow", which proves the lazy path was
// not reached (the canvas is the only artifact of the three.js init).

beforeEach(() => {
  mockMatchMedia(false);
});

// ---------------------------------------------------------------------------
// 1. Root accessibility contract
// ---------------------------------------------------------------------------
describe("BackgroundFX — root element", () => {
  it("is aria-hidden", () => {
    const { container } = render(<BackgroundFX />);
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
  });

  it("has pointer-events:none style", () => {
    const { container } = render(<BackgroundFX />);
    const root = container.firstElementChild as HTMLElement;
    // The inline style is set directly on the root element.
    expect(root.style.pointerEvents).toBe("none");
  });
});

// ---------------------------------------------------------------------------
// 2. Dots layer — always present by default
// ---------------------------------------------------------------------------
describe("BackgroundFX — dots layer (default glow=blobs)", () => {
  it("renders the dots layer element", () => {
    const { container } = render(<BackgroundFX />);
    expect(container.querySelector("[data-bg-layer='dots']")).toBeTruthy();
  });

  it("dots layer carries the animation class when motion is not reduced", () => {
    mockMatchMedia(false);
    const { container } = render(<BackgroundFX />);
    const dots = container.querySelector("[data-bg-layer='dots']") as HTMLElement;
    expect(dots.dataset.motionReduced).toBeUndefined();
  });

  it("dots layer gets data-motion-reduced when prefers-reduced-motion", () => {
    mockMatchMedia(true);
    const { container } = render(<BackgroundFX />);
    const dots = container.querySelector("[data-bg-layer='dots']") as HTMLElement;
    expect(dots.dataset.motionReduced).toBe("true");
  });
});

// ---------------------------------------------------------------------------
// 3. Blobs layer
// ---------------------------------------------------------------------------
describe("BackgroundFX — blobs layer", () => {
  it("renders blobs when glow=blobs (default)", () => {
    const { container } = render(<BackgroundFX glow="blobs" />);
    expect(container.querySelector("[data-bg-layer='blobs']")).toBeTruthy();
  });

  it("renders blobs when glow prop is omitted (default=blobs)", () => {
    const { container } = render(<BackgroundFX />);
    expect(container.querySelector("[data-bg-layer='blobs']")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 4. glow="off" — renders nothing visible
// ---------------------------------------------------------------------------
describe("BackgroundFX — glow=off", () => {
  it("does not render dots when off", () => {
    const { container } = render(<BackgroundFX glow="off" />);
    expect(container.querySelector("[data-bg-layer='dots']")).toBeNull();
  });

  it("does not render blobs when off", () => {
    const { container } = render(<BackgroundFX glow="off" />);
    expect(container.querySelector("[data-bg-layer='blobs']")).toBeNull();
  });

  it("does not render flow canvas when off", () => {
    const { container } = render(<BackgroundFX glow="off" />);
    expect(container.querySelector("[data-bg-layer='flow']")).toBeNull();
  });

  it("root element still exists (aria-hidden wrapper stays)", () => {
    const { container } = render(<BackgroundFX glow="off" />);
    // The root wrapper must be present so the caller can always rely on the element.
    expect(container.firstElementChild).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 5. glow="flow" — structural contract (no real WebGL in jsdom)
// ---------------------------------------------------------------------------
describe("BackgroundFX — glow=flow", () => {
  it("renders the flow container slot", () => {
    const { container } = render(<BackgroundFX glow="flow" />);
    expect(container.querySelector("[data-bg-layer='flow']")).toBeTruthy();
  });

  it("does NOT render blobs when glow=flow", () => {
    const { container } = render(<BackgroundFX glow="flow" />);
    expect(container.querySelector("[data-bg-layer='blobs']")).toBeNull();
  });

  it("still renders dots alongside flow", () => {
    const { container } = render(<BackgroundFX glow="flow" />);
    expect(container.querySelector("[data-bg-layer='dots']")).toBeTruthy();
  });

  it("unmount does not throw (lifecycle cleanup guard)", () => {
    const { unmount } = render(<BackgroundFX glow="flow" />);
    expect(() => act(() => unmount())).not.toThrow();
  });

  it("switching from flow to blobs unmounts without throw", () => {
    const { rerender, unmount } = render(<BackgroundFX glow="flow" />);
    expect(() => act(() => rerender(<BackgroundFX glow="blobs" />))).not.toThrow();
    expect(() => act(() => unmount())).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// 6. three.js is NOT imported for non-flow modes
// ---------------------------------------------------------------------------
describe("BackgroundFX — three.js lazy import guard", () => {
  it("no flow container is rendered for glow=blobs (three not triggered)", () => {
    const { container } = render(<BackgroundFX glow="blobs" />);
    // If three.js were loaded, the flow canvas would be mounted here.
    expect(container.querySelector("[data-bg-layer='flow']")).toBeNull();
  });

  it("no flow container is rendered for glow=off (three not triggered)", () => {
    const { container } = render(<BackgroundFX glow="off" />);
    expect(container.querySelector("[data-bg-layer='flow']")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 7. parseCssColor — pure helper unit tests
// ---------------------------------------------------------------------------
describe("parseCssColor", () => {
  it("parses a 6-digit hex string", () => {
    expect(parseCssColor("#f7f5f2")).toEqual([
      parseInt("f7", 16) / 255,
      parseInt("f5", 16) / 255,
      parseInt("f2", 16) / 255,
    ]);
  });

  it("parses a 3-digit hex string by expanding it", () => {
    const result = parseCssColor("#abc");
    expect(result).toEqual([
      parseInt("aa", 16) / 255,
      parseInt("bb", 16) / 255,
      parseInt("cc", 16) / 255,
    ]);
  });

  it("parses rgb() format", () => {
    expect(parseCssColor("rgb(247, 245, 242)")).toEqual([247 / 255, 245 / 255, 242 / 255]);
  });

  it("parses rgba() format (ignores alpha)", () => {
    expect(parseCssColor("rgba(247, 245, 242, 0.5)")).toEqual([247 / 255, 245 / 255, 242 / 255]);
  });

  it("trims leading/trailing whitespace", () => {
    expect(parseCssColor("  #14130f  ")).toEqual([
      parseInt("14", 16) / 255,
      parseInt("13", 16) / 255,
      parseInt("0f", 16) / 255,
    ]);
  });

  it("returns null for an empty string", () => {
    expect(parseCssColor("")).toBeNull();
  });

  it("returns null for a whitespace-only string", () => {
    expect(parseCssColor("   ")).toBeNull();
  });

  it("returns null for an unrecognised format", () => {
    expect(parseCssColor("hsl(200, 50%, 50%)")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 8. flowPaletteFromTokens — reads CSS vars, falls back on empty
// ---------------------------------------------------------------------------
describe("flowPaletteFromTokens", () => {
  // Helper: stub getComputedStyle to return given props.
  function stubComputedStyle(props: Record<string, string>) {
    const original = window.getComputedStyle;
    Object.defineProperty(window, "getComputedStyle", {
      writable: true,
      value: () => ({
        getPropertyValue: (prop: string) => props[prop] ?? "",
      }),
    });
    return () => {
      Object.defineProperty(window, "getComputedStyle", {
        writable: true,
        value: original,
      });
    };
  }

  it("returns different palettes for light vs dark theme tokens", () => {
    // Light theme: remove "dark" class, supply light-theme token values.
    document.documentElement.classList.remove("dark");
    const restoreLight = stubComputedStyle({
      "--hf-bg": "#f7f5f2",
      "--hf-sage": "#8fa084",
      "--hf-terracotta": "#b8755c",
      "--hf-sage-deep": "#6b7e62",
    });
    const light = flowPaletteFromTokens();
    restoreLight();

    // Dark theme: add "dark" class, supply dark-theme token values.
    document.documentElement.classList.add("dark");
    const restoreDark = stubComputedStyle({
      "--hf-bg": "#14130f",
      "--hf-sage": "#a6b89a",
      "--hf-terracotta": "#cb8b72",
      "--hf-sage-deep": "#8aa07e",
    });
    const dark = flowPaletteFromTokens();
    restoreDark();
    document.documentElement.classList.remove("dark");

    // The two palettes must differ.
    expect(light.bg).not.toEqual(dark.bg);
    expect(light.a).not.toEqual(dark.a);
  });

  it("falls back to hard-coded constants when computed values are empty", () => {
    document.documentElement.classList.remove("dark");
    // Stub returns empty strings for all props (simulates jsdom without CSS).
    const restore = stubComputedStyle({});
    const palette = flowPaletteFromTokens();
    restore();

    // Each channel should be a valid number in [0, 1].
    for (const ch of [...palette.bg, ...palette.a, ...palette.b, ...palette.c]) {
      expect(ch).toBeGreaterThanOrEqual(0);
      expect(ch).toBeLessThanOrEqual(1);
    }
    // Light-mode fallback bg should match #f7f5f2.
    expect(palette.bg[0]).toBeCloseTo(parseInt("f7", 16) / 255, 3);
  });
});

// ---------------------------------------------------------------------------
// 9. Theme-reactivity via MutationObserver — observable contract
// ---------------------------------------------------------------------------
describe("BackgroundFX — theme switch observer", () => {
  it("mutating documentElement class does not throw when glow=flow is mounted", () => {
    const { unmount } = render(<BackgroundFX glow="flow" />);
    expect(() =>
      act(() => {
        document.documentElement.classList.add("dark");
        document.documentElement.classList.remove("dark");
      }),
    ).not.toThrow();
    act(() => unmount());
  });

  it("unmount disconnects the MutationObserver", () => {
    const disconnectSpy = vi.spyOn(MutationObserver.prototype, "disconnect");
    const { unmount } = render(<BackgroundFX glow="flow" />);
    act(() => unmount());
    expect(disconnectSpy).toHaveBeenCalled();
    disconnectSpy.mockRestore();
  });

  it("switching away from flow disconnects the observer (effect cleanup)", () => {
    const disconnectSpy = vi.spyOn(MutationObserver.prototype, "disconnect");
    const { rerender, unmount } = render(<BackgroundFX glow="flow" />);
    act(() => rerender(<BackgroundFX glow="blobs" />));
    // Effect cleanup fires on prop change — observer should be disconnected.
    expect(disconnectSpy).toHaveBeenCalled();
    disconnectSpy.mockRestore();
    act(() => unmount());
  });
});

// ---------------------------------------------------------------------------
// 10. Grain layer — subtle film-grain overlay, gated by the code toggle
// ---------------------------------------------------------------------------
describe("BackgroundFX — grain layer", () => {
  it("renders the grain layer in blobs mode iff grain is enabled", () => {
    const { container } = render(<BackgroundFX glow="blobs" />);
    expect(!!container.querySelector("[data-bg-layer='grain']")).toBe(GRAIN_ENABLED);
  });

  it("renders the grain layer in flow mode iff grain is enabled", () => {
    const { container } = render(<BackgroundFX glow="flow" />);
    expect(!!container.querySelector("[data-bg-layer='grain']")).toBe(GRAIN_ENABLED);
  });

  it("never renders the grain layer when glow=off", () => {
    const { container } = render(<BackgroundFX glow="off" />);
    expect(container.querySelector("[data-bg-layer='grain']")).toBeNull();
  });
});
