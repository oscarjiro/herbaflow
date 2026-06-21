/**
 * Liquid-glass refraction capability detection (one canonical home).
 *
 * The `.hf-glass` recipe (index.css) renders real edge refraction by applying
 * an SVG `feDisplacementMap` filter to a `backdrop-filter` layer. That trick is
 * **Chromium-only**: Safari and Firefox support `filter: url(#id)` in general,
 * so a pure-CSS `@supports (filter: url(...))` test reports a FALSE POSITIVE
 * there and cannot express the split. They do render the displacement, just not
 * on a backdrop target, so the refraction is invisible / broken.
 *
 * Pure CSS therefore cannot key the refraction path correctly. This module is
 * the minimal runtime probe that does: it sets a single attribute on
 * `<html>` ONLY when it can positively confirm a Chromium engine with
 * backdrop-filter support. CSS keys the refraction path off that attribute; the
 * SAFE DEFAULT (no attribute) is the frosted look, never the broken blur.
 */

/** Attribute set on `document.documentElement` when refraction is confirmed. */
export const GLASS_REFRACT_ATTR = "data-glass-refract";

type UABrand = { brand: string; version: string };
type NavigatorWithUAData = Navigator & {
  userAgentData?: { brands?: UABrand[] };
};

/** True only for a Chromium-family engine (excludes Safari/Firefox). */
function isChromium(): boolean {
  if (typeof navigator === "undefined") return false;

  // Preferred: the structured UA-Client-Hints brand list (Chromium-only API).
  const nav = navigator as NavigatorWithUAData;
  const brands = nav.userAgentData?.brands;
  if (Array.isArray(brands)) {
    return brands.some((b) => /Chromium|Google Chrome|Microsoft Edge/i.test(b.brand));
  }

  // Fallback: UA string. Chrome/Chromium/Edge/Opera all carry "Chrome";
  // Safari and Firefox do not — Safari's UA has no "Chrome" token, and any
  // engine reporting itself as Firefox/FxiOS is excluded explicitly.
  const ua = nav.userAgent ?? "";
  if (/\b(Firefox|FxiOS)\b/.test(ua)) return false;
  return /\bChrome\b|\bChromium\b|\bCriOS\b/.test(ua);
}

/**
 * Returns true only when the engine can render backdrop refraction (Chromium +
 * backdrop-filter support). Any uncertainty — Safari, Firefox, missing
 * `CSS.supports`, SSR — returns false so the surface stays frosted.
 */
export function detectRefractionSupport(): boolean {
  if (typeof CSS === "undefined" || typeof CSS.supports !== "function") return false;
  if (
    !CSS.supports("backdrop-filter", "blur(2px)") &&
    !CSS.supports("-webkit-backdrop-filter", "blur(2px)")
  ) {
    return false;
  }
  return isChromium();
}

/**
 * Toggle the refraction attribute on `<html>` based on detection. No-op under
 * SSR / when there is no document. Idempotent: removes a stale attribute when
 * detection no longer confirms refraction.
 */
export function applyGlassSupport(): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (detectRefractionSupport()) {
    root.setAttribute(GLASS_REFRACT_ATTR, "on");
  } else {
    root.removeAttribute(GLASS_REFRACT_ATTR);
  }
}
