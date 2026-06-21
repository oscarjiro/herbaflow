import { cn } from "@/lib/cn";
import type { HTMLAttributes, ReactNode } from "react";

export type GlassTier = "chrome" | "overlay" | "raised";

interface GlassSurfaceProps extends HTMLAttributes<HTMLDivElement> {
  /** Visual tier — controls tint/shine strength and hover behaviour.
   *  chrome  = nav bars, pill buttons (thinner tint, strong blur)
   *  overlay = dialogs, popovers, menus (stronger tint)
   *  raised  = stat cards, timeline cards (standard tint + hover lift)
   *  Default: overlay */
  tier?: GlassTier;
  children?: ReactNode;
}

export function GlassSurface({
  tier = "overlay",
  children,
  className,
  ...props
}: GlassSurfaceProps) {
  return (
    <div className={cn("hf-glass", `hf-glass--${tier}`, className)} {...props}>
      {/* Layer 0: refraction — frosted backdrop blur by default (Safari/Firefox
          and any unconfirmed engine); real SVG displacement is opted in for
          Chromium only via html[data-glass-refract="on"] (lib/glassSupport.ts) */}
      <div className="hf-glass__refract" aria-hidden="true" />
      {/* Layer 1: tint wash — semi-transparent fill; strength varies by tier */}
      <div className="hf-glass__tint" aria-hidden="true" />
      {/* Layer 2: rim-light / shine — inset box-shadow highlights */}
      <div className="hf-glass__shine" aria-hidden="true" />
      {/* Layer 3: content slot */}
      <div className="hf-glass__content">{children}</div>
    </div>
  );
}
