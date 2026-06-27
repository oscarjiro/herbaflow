import { describe, expect, test } from "vitest";
import { SMOOTH_SCROLL_ENABLED, isSmoothScrollRoute, shouldSmoothScroll } from "./smoothScroll";

describe("isSmoothScrollRoute", () => {
  test("enables inertial scroll on the Landing route", () => {
    expect(isSmoothScrollRoute("/")).toBe(true);
  });

  test("enables inertial scroll on the About route", () => {
    expect(isSmoothScrollRoute("/about")).toBe(true);
  });

  test("tolerates a trailing slash on About", () => {
    expect(isSmoothScrollRoute("/about/")).toBe(true);
  });

  test("keeps native scroll on the analysis entry route", () => {
    expect(isSmoothScrollRoute("/analysis")).toBe(false);
  });

  test("keeps native scroll on a run route", () => {
    expect(isSmoothScrollRoute("/analysis/abc123")).toBe(false);
  });

  test("keeps native scroll on a stage route", () => {
    expect(isSmoothScrollRoute("/analysis/abc123/3")).toBe(false);
  });

  test("keeps native scroll on any unknown route", () => {
    expect(isSmoothScrollRoute("/whatever")).toBe(false);
  });
});

describe("shouldSmoothScroll", () => {
  test("follows the code toggle on a marketing route without reduced motion", () => {
    expect(shouldSmoothScroll("/", false)).toBe(SMOOTH_SCROLL_ENABLED);
  });

  test("never smooth-scrolls when the user prefers reduced motion", () => {
    expect(shouldSmoothScroll("/", true)).toBe(false);
    expect(shouldSmoothScroll("/about", true)).toBe(false);
  });

  test("never smooth-scrolls on analysis routes regardless of preference", () => {
    expect(shouldSmoothScroll("/analysis/abc123", false)).toBe(false);
    expect(shouldSmoothScroll("/analysis/abc123/3", false)).toBe(false);
  });
});
