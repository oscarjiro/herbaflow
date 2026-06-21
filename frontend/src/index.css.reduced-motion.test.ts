/**
 * Global reduced-motion guard — CSS assertions.
 *
 * The design system mandates that every motion respects
 * `prefers-reduced-motion`. Per-component guards exist (.hf-ink-focus, the
 * background blobs/flow), but tailwindcss-animate entrance animations
 * (animate-in / zoom / fade) and arbitrary transitions on primitives such as
 * Select are NOT individually guarded. A single global guard neutralizes all
 * non-essential motion for users who request reduced motion — one canonical
 * home rather than a per-component opt-in.
 *
 * jsdom cannot evaluate `prefers-reduced-motion`, so we assert the rule text
 * in index.css rather than testing computed styles.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const cssRaw = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");

// Isolate the global guard block by its marker comment so assertions target it
// (not the scoped .hf-ink-focus / blob reduced-motion blocks).
function globalGuardBlock(): string {
  const marker = cssRaw.indexOf("Global reduced-motion guard");
  expect(marker).toBeGreaterThan(-1);
  const mediaStart = cssRaw.indexOf("@media (prefers-reduced-motion: reduce)", marker);
  expect(mediaStart).toBeGreaterThan(-1);
  return cssRaw.slice(mediaStart, mediaStart + 600);
}

describe("global reduced-motion guard", () => {
  it("declares a global guard block with the marker comment", () => {
    expect(cssRaw).toMatch(/Global reduced-motion guard/);
  });

  it("targets all elements (universal selector incl. pseudo-elements)", () => {
    const block = globalGuardBlock();
    expect(block).toMatch(/\*\s*,\s*\*::before\s*,\s*\*::after/);
  });

  it("neutralizes animation duration with !important", () => {
    const block = globalGuardBlock();
    expect(block).toMatch(/animation-duration:\s*0\.01ms\s*!important/);
  });

  it("forces animation-iteration-count to 1 so loops do not persist", () => {
    const block = globalGuardBlock();
    expect(block).toMatch(/animation-iteration-count:\s*1\s*!important/);
  });

  it("neutralizes transition duration with !important", () => {
    const block = globalGuardBlock();
    expect(block).toMatch(/transition-duration:\s*0\.01ms\s*!important/);
  });

  it("disables smooth scroll-behavior", () => {
    const block = globalGuardBlock();
    expect(block).toMatch(/scroll-behavior:\s*auto\s*!important/);
  });
});
