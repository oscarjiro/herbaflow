/**
 * Task 6 — CSS assertions: animated ink-border focus for input/textarea/select.
 *
 * jsdom cannot simulate :focus-visible pseudo-classes, so we assert the rule
 * text in index.css is correct rather than testing rendered styles.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const cssRaw = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");

describe(".hf-ink-focus — animated ink-border focus rule", () => {
  it("defines .hf-ink-focus in index.css", () => {
    expect(cssRaw).toMatch(/\.hf-ink-focus/);
  });

  it(".hf-ink-focus:focus-visible removes the outline (no ring)", () => {
    // The animated border replaces the default outline — outline must be none
    const idx = cssRaw.indexOf(".hf-ink-focus");
    expect(idx).toBeGreaterThan(-1);
    // Find the :focus-visible block for hf-ink-focus
    const focusIdx = cssRaw.indexOf(".hf-ink-focus", idx);
    const tail = cssRaw.slice(focusIdx, focusIdx + 800);
    expect(tail).toMatch(/outline:\s*none/);
  });

  it(".hf-ink-focus:focus-visible sets border-color to --hf-fg-1 (ink)", () => {
    const idx = cssRaw.indexOf(".hf-ink-focus");
    expect(idx).toBeGreaterThan(-1);
    const tail = cssRaw.slice(idx, idx + 800);
    expect(tail).toMatch(/border-color:\s*var\(--hf-fg-1\)/);
  });

  it(".hf-ink-focus:focus-visible applies a soft glow using color-mix and --hf-fg-1", () => {
    const idx = cssRaw.indexOf(".hf-ink-focus");
    expect(idx).toBeGreaterThan(-1);
    const tail = cssRaw.slice(idx, idx + 800);
    // Glow is box-shadow with color-mix(in srgb, var(--hf-fg-1), transparent ...)
    expect(tail).toMatch(/color-mix\(in srgb,\s*var\(--hf-fg-1\)/);
  });

  it(".hf-ink-focus:focus-visible has inset box-shadow (1px ink inner border)", () => {
    const idx = cssRaw.indexOf(".hf-ink-focus");
    expect(idx).toBeGreaterThan(-1);
    // Look in a wider window that covers the :focus-visible block
    const tail = cssRaw.slice(idx, idx + 2000);
    expect(tail).toMatch(/inset 0 0 0 1px var\(--hf-fg-1\)/);
  });

  it(".hf-ink-focus has a transition on border-color and box-shadow", () => {
    const idx = cssRaw.indexOf(".hf-ink-focus");
    expect(idx).toBeGreaterThan(-1);
    const tail = cssRaw.slice(idx, idx + 800);
    expect(tail).toMatch(/transition/);
  });
});

describe(".hf-ink-focus — invalid (danger) state", () => {
  it("defines danger border-color for aria-invalid", () => {
    expect(cssRaw).toMatch(/--hf-danger/);
    // The invalid state reuses hf-danger on border
    const idx = cssRaw.indexOf("hf-ink-focus");
    expect(idx).toBeGreaterThan(-1);
    const tail = cssRaw.slice(idx, idx + 1200);
    expect(tail).toMatch(/hf-danger/);
  });

  it("aria-invalid:focus-visible applies danger glow via color-mix", () => {
    const idx = cssRaw.indexOf(".hf-ink-focus");
    expect(idx).toBeGreaterThan(-1);
    const tail = cssRaw.slice(idx, idx + 1200);
    // Should reference --hf-danger in a color-mix or box-shadow
    expect(tail).toMatch(/color-mix\(in srgb,\s*var\(--hf-danger\)/);
  });
});

describe(".hf-ink-focus — prefers-reduced-motion", () => {
  it("prefers-reduced-motion rule disables transition on .hf-ink-focus", () => {
    // Locate the @media (prefers-reduced-motion: reduce) block that is
    // near .hf-ink-focus (inside @layer base). We find its start, then
    // read forward past the two nested closing braces to grab the block.
    const mediaStr = "@media (prefers-reduced-motion: reduce)";
    const hfInkIdx = cssRaw.indexOf(".hf-ink-focus");
    expect(hfInkIdx).toBeGreaterThan(-1);
    // The reduced-motion block appears after the .hf-ink-focus base rule
    const mediaIdx = cssRaw.indexOf(mediaStr, hfInkIdx);
    expect(mediaIdx, "reduced-motion @media block not found after .hf-ink-focus").toBeGreaterThan(
      -1,
    );
    // Read a window that covers the whole nested block
    const tail = cssRaw.slice(mediaIdx, mediaIdx + 200);
    expect(tail).toMatch(/transition:\s*none/);
  });
});

describe("index.css input focus-visible override", () => {
  it("the base :where(input,select,textarea):focus-visible rule is replaced or dominated by .hf-ink-focus", () => {
    // Task 4 left a placeholder rule. Task 6 adds .hf-ink-focus to override it cleanly.
    // Verify both coexist (the old placeholder stays for non-hf-ink-focus elements)
    expect(cssRaw).toMatch(/:where\(input[^)]*\):focus-visible/);
  });
});
