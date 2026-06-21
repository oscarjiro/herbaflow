import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Read the stylesheet's literal text. vitest runs with the frontend package as its working
// directory, so a cwd-relative path reads the real token declarations without depending on
// import.meta URL scheme or Vite's ?raw loader (both behave inconsistently in this runner).
const cssRaw = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");

// The semantic ramp that MUST differ between light (:root) and dark (.dark). Adding a themeable
// surface/text/status token without a .dark override is the regression this guard catches.
const REQUIRED = [
  "--hf-bg",
  "--hf-surface",
  "--hf-surface-2",
  "--hf-fg-1",
  "--hf-fg-2",
  "--hf-fg-3",
  "--hf-fg-4",
  "--hf-border",
  "--hf-border-strong",
  "--hf-success",
  "--hf-success-soft",
  "--hf-warning",
  "--hf-warning-soft",
  "--hf-danger",
  "--hf-danger-soft",
  "--hf-info",
  "--hf-info-soft",
];

// New liquid-glass tokens: must be defined in both :root and .dark and differ between them
// (raw CSS string must differ — tokens that use `var()` indirection are tested separately).
const GLASS_TOKENS = [
  "--hf-bg-raised",
  "--hf-glass-tint",
  "--hf-glass-tint-strong",
  "--hf-glass-shine",
  "--hf-glass-shine-2",
  "--hf-glass-shadow",
  "--hf-dot",
];

function block(css: string, selector: string): string {
  const start = css.indexOf(selector + " {");
  if (start === -1) throw new Error(`selector ${selector} not found`);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  return css.slice(open + 1, close);
}
function value(blockText: string, token: string): string | null {
  const m = blockText.match(new RegExp(`${token}\\s*:\\s*([^;]+);`));
  return m?.[1]?.trim() ?? null;
}

describe("hf-* dark ramp parity", () => {
  const root = block(cssRaw, ":root");
  const dark = block(cssRaw, ".dark");

  it.each(REQUIRED)("%s is defined in both :root and .dark and differs", (token) => {
    const light = value(root, token);
    const night = value(dark, token);
    expect(light, `${token} missing in :root`).toBeTruthy();
    expect(night, `${token} missing in .dark`).toBeTruthy();
    expect(night).not.toBe(light);
  });
});

describe("liquid-glass token parity", () => {
  const root = block(cssRaw, ":root");
  const dark = block(cssRaw, ".dark");

  it.each(GLASS_TOKENS)("%s is defined in both :root and .dark and differs", (token) => {
    const light = value(root, token);
    const night = value(dark, token);
    expect(light, `${token} missing in :root`).toBeTruthy();
    expect(night, `${token} missing in .dark`).toBeTruthy();
    expect(night).not.toBe(light);
  });
});

describe("--hf-accent token", () => {
  // --hf-accent uses `var(--hf-fg-1)` in both light and dark (same indirection string).
  // The resolved value differs at runtime because --hf-fg-1 is overridden in .dark.
  // This test only asserts presence (not raw-string inequality).
  const root = block(cssRaw, ":root");
  const dark = block(cssRaw, ".dark");

  it("--hf-accent is defined in :root", () => {
    expect(value(root, "--hf-accent"), "--hf-accent missing in :root").toBeTruthy();
  });
  it("--hf-accent is defined in .dark", () => {
    expect(value(dark, "--hf-accent"), "--hf-accent missing in .dark").toBeTruthy();
  });
});

describe("radius tokens", () => {
  const root = block(cssRaw, ":root");

  it("--radius-sm is 8px (softer scale)", () => {
    // --radius-sm is set in @theme inline, not :root — check the full CSS text
    expect(cssRaw).toMatch(/--radius-sm\s*:\s*8px/);
  });
  it("--radius-md is 11px", () => {
    expect(cssRaw).toMatch(/--radius-md\s*:\s*11px/);
  });
  it("--radius-lg is 16px", () => {
    expect(cssRaw).toMatch(/--radius-lg\s*:\s*16px/);
  });
  it("--radius-pill is 999px", () => {
    const v = value(root, "--radius-pill");
    expect(v).toBe("999px");
  });
});

describe("motion ease alias", () => {
  it("--ease is defined", () => {
    expect(cssRaw).toMatch(/--ease\s*:\s*cubic-bezier/);
  });
});

describe("base element styles are layered so utilities win", () => {
  // The element resets (a/p/h*/html/body) must live inside @layer base. Left unlayered they outrank
  // Tailwind's @layer utilities, so a `text-hf-*` utility on a link/heading is ignored and a
  // link-button's text color collapses onto its own background (the invisible-control defect).
  it("nests the `a { color: inherit }` reset inside a layer, not at top level", () => {
    const idx = cssRaw.search(/\n\s*a\s*\{\s*\n?\s*color:\s*inherit/);
    expect(idx, "`a { color: inherit }` reset not found").toBeGreaterThan(-1);
    let depth = 0;
    for (let i = 0; i < idx; i++) {
      if (cssRaw[i] === "{") depth++;
      else if (cssRaw[i] === "}") depth--;
    }
    expect(depth, "`a` reset must be nested inside @layer base, not unlayered").toBeGreaterThan(0);
  });
});
