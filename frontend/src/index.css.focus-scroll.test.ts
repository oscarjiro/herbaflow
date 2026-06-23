/**
 * Focus, scrollbars, and hidden page scrollbar — CSS assertions.
 *
 * All assertions read the literal CSS text (same pattern as index.css.theme.test.ts).
 * jsdom cannot compute :focus-visible styles, so we assert the rules are present and
 * well-formed in the source CSS rather than simulating keyboard interaction.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const cssRaw = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");

// ---------------------------------------------------------------------------
// Focus ring
// ---------------------------------------------------------------------------

describe("refined focus-visible ring", () => {
  it("focus-visible rule exists in index.css", () => {
    expect(cssRaw).toMatch(/:focus-visible/);
  });

  it("focus-visible ring uses --hf-fg-1 (ink colour)", () => {
    // The ring colour must be a token, not raw hex
    const focusBlock = cssRaw.match(/:focus-visible\s*\{[^}]+\}/);
    expect(focusBlock, ":focus-visible block not found").toBeTruthy();
    expect(focusBlock![0]).toContain("--hf-fg-1");
  });

  it("focus-visible ring uses a softened radius token (--radius-md or larger)", () => {
    // Must NOT use --radius-0 / --radius-1 (the old sharp values)
    const focusBlock = cssRaw.match(/:focus-visible\s*\{[^}]+\}/);
    expect(focusBlock, ":focus-visible block not found").toBeTruthy();
    // Soft radius: --radius-md (11px) used for the refined ring
    expect(focusBlock![0]).toMatch(/--radius-md/);
  });

  it("focus-visible rule does NOT use --radius-1 (the old sharp 2px radius)", () => {
    const focusBlock = cssRaw.match(/:focus-visible\s*\{[^}]+\}/);
    expect(focusBlock, ":focus-visible block not found").toBeTruthy();
    expect(focusBlock![0]).not.toMatch(/var\(--radius-1\)/);
  });

  it("focus-visible rule is inside @layer base (depth > 0)", () => {
    const idx = cssRaw.search(/:focus-visible/);
    expect(idx, ":focus-visible not found").toBeGreaterThan(-1);
    let depth = 0;
    for (let i = 0; i < idx; i++) {
      if (cssRaw[i] === "{") depth++;
      else if (cssRaw[i] === "}") depth--;
    }
    expect(depth, ":focus-visible must be nested inside @layer base").toBeGreaterThan(0);
  });

  it("outline is softer (1.5px or similar) rather than the old hard 2px", () => {
    const focusBlock = cssRaw.match(/:focus-visible\s*\{[^}]+\}/);
    expect(focusBlock, ":focus-visible block not found").toBeTruthy();
    // The refined spec uses 1.5px outline width
    expect(focusBlock![0]).toMatch(/1\.5px/);
  });
});

// ---------------------------------------------------------------------------
// Thin internal scrollbar utility
// ---------------------------------------------------------------------------

describe(".scroll utility class", () => {
  it(".scroll class exists in index.css", () => {
    expect(cssRaw).toMatch(/\.scroll\s*\{/);
  });

  it(".scroll uses scrollbar-width: thin (Firefox)", () => {
    const scrollBlock = cssRaw.match(/\.scroll\s*\{[^}]+\}/);
    expect(scrollBlock, ".scroll block not found").toBeTruthy();
    expect(scrollBlock![0]).toContain("scrollbar-width: thin");
  });

  it(".scroll uses scrollbar-color with --hf-* tokens (Firefox)", () => {
    const scrollBlock = cssRaw.match(/\.scroll\s*\{[^}]+\}/);
    expect(scrollBlock, ".scroll block not found").toBeTruthy();
    expect(scrollBlock![0]).toMatch(/scrollbar-color:\s*var\(--hf-/);
  });

  it(".scroll sets overflow-y: auto (enables scrolling)", () => {
    const scrollBlock = cssRaw.match(/\.scroll\s*\{[^}]+\}/);
    expect(scrollBlock, ".scroll block not found").toBeTruthy();
    expect(scrollBlock![0]).toContain("overflow-y: auto");
  });

  it("webkit scrollbar track uses --hf-* token (no raw hex)", () => {
    // ::-webkit-scrollbar-track inside/near .scroll block
    expect(cssRaw).toMatch(/::-webkit-scrollbar-track/);
    // The track background must reference an hf token
    const trackIdx = cssRaw.indexOf("::-webkit-scrollbar-track");
    const trackBlock = cssRaw.slice(trackIdx, cssRaw.indexOf("}", trackIdx) + 1);
    expect(trackBlock).toMatch(/var\(--hf-/);
  });

  it("webkit scrollbar thumb uses --hf-* token (no raw hex)", () => {
    expect(cssRaw).toMatch(/::-webkit-scrollbar-thumb/);
    const thumbIdx = cssRaw.indexOf("::-webkit-scrollbar-thumb");
    const thumbBlock = cssRaw.slice(thumbIdx, cssRaw.indexOf("}", thumbIdx) + 1);
    expect(thumbBlock).toMatch(/var\(--hf-/);
  });
});

// ---------------------------------------------------------------------------
// Hidden document (page) scrollbar
// ---------------------------------------------------------------------------

describe("hidden document scrollbar", () => {
  it("html element hides its scrollbar (scrollbar-width: none)", () => {
    // The document-level hide must be on html or :root scoped, not on .scroll
    expect(cssRaw).toMatch(/scrollbar-width:\s*none/);
  });

  it("::-webkit-scrollbar rule for document (width: 0) exists", () => {
    // ::-webkit-scrollbar { width: 0 } scoped to html or global
    expect(cssRaw).toMatch(/::-webkit-scrollbar\s*\{[^}]*width:\s*0[^}]*\}/);
  });

  it("hidden scrollbar rule is inside @layer base", () => {
    const idx = cssRaw.search(/scrollbar-width:\s*none/);
    expect(idx, "scrollbar-width: none not found").toBeGreaterThan(-1);
    let depth = 0;
    for (let i = 0; i < idx; i++) {
      if (cssRaw[i] === "{") depth++;
      else if (cssRaw[i] === "}") depth--;
    }
    expect(depth, "scrollbar-width: none must be inside @layer base").toBeGreaterThan(0);
  });
});
