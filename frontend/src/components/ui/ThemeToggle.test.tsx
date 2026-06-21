import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach, afterAll } from "vitest";
import { hasReducedMotionListener } from "motion/react";
import { ThemeProvider } from "@/lib/theme";
import { ThemeToggle } from "./ThemeToggle";

// ---------------------------------------------------------------------------
// matchMedia stub — jsdom has none. `useReducedMotion` (motion/react) reads
// window.matchMedia("(prefers-reduced-motion)") ONCE and caches the result in
// a module-level singleton (hasReducedMotionListener). To drive the hook per
// test we (1) set matchMedia to the desired preference, then (2) reset the
// singleton so the hook re-initialises against the fresh mock on next render.
// Same pattern as AiLoader.test.tsx.
// ---------------------------------------------------------------------------
function setReducedMotion(reducedMotion: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: query.includes("prefers-reduced-motion")
        ? reducedMotion
        : query.includes("prefers-color-scheme: dark")
          ? false
          : false,
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
  localStorage.clear();
  setReducedMotion(false);
});

// Leave the shared motion singleton in the non-reduced state for any test file
// that runs after this one in the same worker.
afterAll(() => {
  setReducedMotion(false);
});

describe("ThemeToggle — cycle and persist", () => {
  it("cycles system → light → dark → system and persists to localStorage", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    const btn = screen.getByRole("button", { name: /theme:/i });
    expect(btn).toHaveAttribute("aria-label", expect.stringContaining("system"));
    fireEvent.click(btn);
    expect(localStorage.getItem("hf-theme")).toBe("light");
    fireEvent.click(btn);
    expect(localStorage.getItem("hf-theme")).toBe("dark");
    fireEvent.click(btn);
    expect(localStorage.getItem("hf-theme")).toBe("system");
  });

  it("aria-label advances with each cycle", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    const btn = screen.getByRole("button", { name: /theme:/i });
    expect(btn.getAttribute("aria-label")).toContain("system");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-label")).toContain("light");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-label")).toContain("dark");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-label")).toContain("system");
  });
});

describe("ThemeToggle — reduced-motion guard", () => {
  it("icon wrapper carries data-motion-reduced='true' when motion is reduced", () => {
    setReducedMotion(true);
    const { container } = render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    const wrapper = container.querySelector("[data-motion-reduced='true']");
    expect(wrapper).toBeTruthy();
  });

  it("icon wrapper has no data-motion-reduced attribute when motion is not reduced", () => {
    setReducedMotion(false);
    const { container } = render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    const wrapper = container.querySelector("[data-motion-reduced='true']");
    expect(wrapper).toBeNull();
  });
});

describe("ThemeToggle — OS live tracking while pref=system", () => {
  it("resolved theme tracks matchMedia change event while pref is system", () => {
    // Start with system pref; matchMedia initially reports light (not dark).
    let darkMatches = false;
    let changeListener: ((e: MediaQueryListEvent) => void) | null = null;

    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (query: string) => {
        if (query.includes("prefers-color-scheme: dark")) {
          return {
            matches: darkMatches,
            media: query,
            onchange: null,
            addListener: () => {},
            removeListener: () => {},
            addEventListener: (_: string, fn: (e: MediaQueryListEvent) => void) => {
              changeListener = fn;
            },
            removeEventListener: () => {},
            dispatchEvent: () => false,
          };
        }
        // prefers-reduced-motion: not reduced
        return {
          matches: false,
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        };
      },
    });
    hasReducedMotionListener.current = false;

    const { container } = render(
      <ThemeProvider>
        <ThemeToggle />
        {/* Sentinel to read resolved class on documentElement */}
      </ThemeProvider>,
    );

    // Initially system pref + light OS → no `.dark` class
    expect(document.documentElement.classList.contains("dark")).toBe(false);

    // Simulate OS switching to dark — wrap in act() so React flushes the state update
    darkMatches = true;
    act(() => {
      if (changeListener) {
        (changeListener as (e: MediaQueryListEvent) => void)({
          matches: true,
        } as MediaQueryListEvent);
      }
    });

    // ThemeProvider listens and should have toggled the .dark class
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    // Cleanup
    document.documentElement.classList.remove("dark");
    void container; // suppress unused warning
  });
});
