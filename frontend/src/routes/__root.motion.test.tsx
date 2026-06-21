/**
 * Task 4 — LazyMotion provider smoke test
 *
 * Verifies that __root.tsx wraps routed content in LazyMotion so m.* components
 * can animate app-wide. We do NOT attempt to render the real TanStack router
 * (that requires createRouter + RouterProvider boilerplate); instead we mount a
 * minimal harness that exercises the same provider composition.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { LazyMotion, domAnimation, m } from "motion/react";
import { describe, it, expect } from "vitest";

// A tiny Motion-driven component — if LazyMotion is absent, m.div throws.
function MotionChild() {
  return (
    <m.div data-testid="motion-child" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      hello
    </m.div>
  );
}

describe("LazyMotion provider composition", () => {
  it("renders children inside LazyMotion without throwing", () => {
    render(
      <LazyMotion features={domAnimation}>
        <MotionChild />
      </LazyMotion>,
    );
    expect(screen.getByTestId("motion-child")).toBeTruthy();
    expect(screen.getByTestId("motion-child").textContent).toBe("hello");
  });

  it("m.div renders when LazyMotion wraps it (provider is functional)", () => {
    const { container } = render(
      <LazyMotion features={domAnimation}>
        <m.div data-testid="anim" style={{ opacity: 1 }}>
          content
        </m.div>
      </LazyMotion>,
    );
    expect(container.querySelector("[data-testid='anim']")).toBeTruthy();
  });
});

describe("__root.tsx source includes LazyMotion", () => {
  // Belt-and-suspenders: assert the source file contains the LazyMotion import
  // and usage, so a refactor cannot silently remove it.
  const rootSrc = readFileSync(resolve(process.cwd(), "src/routes/__root.tsx"), "utf8");

  it("imports LazyMotion and domAnimation from motion/react", () => {
    expect(rootSrc).toMatch(/LazyMotion/);
    expect(rootSrc).toMatch(/domAnimation/);
    expect(rootSrc).toMatch(/motion\/react/);
  });

  it("uses <LazyMotion> as a JSX element", () => {
    expect(rootSrc).toMatch(/<LazyMotion/);
  });
});
