/**
 * LandingHeroFallback — the static stand-in for the live ASCII-DNA hero.
 *
 * Renders when WebGL is unavailable, when `prefers-reduced-motion: reduce`, or
 * when the model/renderer fails to load. It must read as complete without the
 * live model: a feathered dotted field tinted with the ink token, behind the
 * hero content. Decorative only: aria-hidden, pointer-events:none.
 *
 * The dotted recipe and edge-fade live in the `.hf-dna*` CSS home (index.css);
 * this component only assembles the layer (no parallel styling).
 */

import { cn } from "@/lib/cn";

export function LandingHeroFallback({ className }: { className?: string }) {
  return (
    <div
      data-landing-hero="fallback"
      aria-hidden="true"
      style={{ pointerEvents: "none" }}
      className={cn("hf-dna__fallback", className)}
    />
  );
}
