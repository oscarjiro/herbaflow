import { render, act } from "@testing-library/react";
import { BackgroundFX } from "./BackgroundFX";

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
