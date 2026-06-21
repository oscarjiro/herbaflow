import { render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach, afterAll } from "vitest";
import { hasReducedMotionListener } from "motion/react";
import { AiLoader } from "./AiLoader";

// ---------------------------------------------------------------------------
// matchMedia stub — jsdom has none. `useReducedMotion` (motion/react) reads
// window.matchMedia("(prefers-reduced-motion)") ONCE and caches the result in
// a module-level singleton (hasReducedMotionListener). To drive the hook per
// test we (1) set matchMedia to the desired preference, then (2) reset the
// singleton so the hook re-initialises against the fresh mock on next render.
// Same matchMedia-mock shape as BackgroundFX.test.tsx.
// ---------------------------------------------------------------------------
function setReducedMotion(reducedMotion: boolean) {
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
  // Force motion's lazy reduced-motion init to run again against this mock.
  hasReducedMotionListener.current = false;
}

beforeEach(() => {
  setReducedMotion(false);
});

// Leave the shared motion singleton in the non-reduced state for any test file
// that runs after this one in the same worker.
afterAll(() => {
  setReducedMotion(false);
});

describe("AiLoader — structure", () => {
  it("renders the orb element", () => {
    const { container } = render(<AiLoader />);
    expect(container.querySelector("[data-ai-orb]")).toBeTruthy();
  });

  it("renders a label region with the status role", () => {
    render(<AiLoader />);
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("renders the orb with the glossy base class (token-driven gloss)", () => {
    const { container } = render(<AiLoader />);
    const orb = container.querySelector("[data-ai-orb]") as HTMLElement;
    expect(orb.className).toContain("hf-ai-orb");
  });
});

describe("AiLoader — animated (motion NOT reduced)", () => {
  it("orb carries the spin animation class", () => {
    setReducedMotion(false);
    const { container } = render(<AiLoader />);
    const orb = container.querySelector("[data-ai-orb]") as HTMLElement;
    expect(orb.className).toContain("animate-[hf-orb-spin");
    expect(orb.dataset.motionReduced).toBeUndefined();
  });

  it("each label letter carries the pulse animation class", () => {
    setReducedMotion(false);
    const { container } = render(<AiLoader />);
    const letters = container.querySelectorAll("[data-ai-letter]");
    expect(letters.length).toBeGreaterThan(0);
    letters.forEach((letter) => {
      expect((letter as HTMLElement).className).toContain("animate-[hf-letter-pulse");
    });
  });
});

describe("AiLoader — reduced motion (static branch)", () => {
  it("orb DROPS the spin animation class and is marked reduced", () => {
    setReducedMotion(true);
    const { container } = render(<AiLoader />);
    const orb = container.querySelector("[data-ai-orb]") as HTMLElement;
    expect(orb.className).not.toContain("animate-[hf-orb-spin");
    expect(orb.dataset.motionReduced).toBe("true");
  });

  it("label letters DROP the pulse animation class", () => {
    setReducedMotion(true);
    const { container } = render(<AiLoader />);
    const letters = container.querySelectorAll("[data-ai-letter]");
    expect(letters.length).toBeGreaterThan(0);
    letters.forEach((letter) => {
      expect((letter as HTMLElement).className).not.toContain("animate-[hf-letter-pulse");
    });
  });

  it("orb still carries the glossy base class in the static branch", () => {
    setReducedMotion(true);
    const { container } = render(<AiLoader />);
    const orb = container.querySelector("[data-ai-orb]") as HTMLElement;
    expect(orb.className).toContain("hf-ai-orb");
  });
});

describe("AiLoader — label content", () => {
  it("shows a default plain-English status phrase", () => {
    render(<AiLoader />);
    // Letters render as separate spans; the clean phrase lives on aria-label.
    expect(screen.getByRole("status").getAttribute("aria-label")).toBe("Analyzing");
  });

  it("accepts a custom set of phrases and renders the first", () => {
    render(<AiLoader phrases={["Building network"]} />);
    expect(screen.getByRole("status").getAttribute("aria-label")).toBe("Building network");
  });

  it("never emits an em dash in the label copy", () => {
    render(<AiLoader phrases={["Scoring targets"]} />);
    expect(screen.getByRole("status").getAttribute("aria-label")).not.toContain("—");
  });
});
