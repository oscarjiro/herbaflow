/**
 * Smooth-scroll policy — the one home that decides where inertial scrolling runs.
 *
 * We use Lenis (`lenis/react`) for inertial smoothing on the presentational pages
 * (Landing + About) only. The analysis pages keep native scrolling, because their
 * data tables and live-polling views behave best with the browser's own scroll.
 *
 * Lenis drives scroll in JS (transform-based), so the global
 * `@media (prefers-reduced-motion) { scroll-behavior: auto }` rule in index.css does
 * NOT disable it. Reduced motion is therefore gated here in JS instead.
 *
 * SMOOTH_SCROLL_ENABLED is a deliberate code toggle (no UI): flip it to disable
 * inertial scrolling everywhere without touching the wiring in __root.
 */
import type { LenisOptions } from "lenis";

/** Master code toggle for inertial smooth scrolling. */
export const SMOOTH_SCROLL_ENABLED = true;

/** Routes that get inertial smoothing. Everything else stays native. */
const SMOOTH_SCROLL_ROUTES = ["/", "/about"];

/** Subtle inertial feel; touch scrolling stays native (best on mobile). */
export const SMOOTH_SCROLL_OPTIONS: LenisOptions = {
  lerp: 0.1,
  smoothWheel: true,
};

/** Strip a trailing slash from a path, keeping the root "/" intact. */
function normalizePath(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
}

/** True for the presentational routes (Landing + About), false elsewhere. */
export function isSmoothScrollRoute(pathname: string): boolean {
  return SMOOTH_SCROLL_ROUTES.includes(normalizePath(pathname));
}

/**
 * Whether inertial smooth scrolling should be active for the current view:
 * enabled by the code toggle, not overridden by reduced-motion, and on a
 * presentational route.
 */
export function shouldSmoothScroll(pathname: string, reducedMotion: boolean): boolean {
  return SMOOTH_SCROLL_ENABLED && !reducedMotion && isSmoothScrollRoute(pathname);
}
