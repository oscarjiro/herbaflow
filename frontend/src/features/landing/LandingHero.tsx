/**
 * LandingHero — the signature Landing backdrop: a Draco-compressed `dna.glb`
 * rendered to a live ASCII grid via three.js, themed with the ink token and
 * sitting behind the hero content at low opacity.
 *
 * This component owns only the fixed, masked, aria-hidden, pointer-events:none
 * backdrop LAYER. The three.js lifecycle lives in `useAsciiDna` (the one
 * canonical lazy-three home pattern, mirroring BackgroundFX). three.js is
 * imported ONLY inside that hook's effect, so it stays in a Landing-only lazy
 * chunk and never enters the app shell bundle.
 *
 * When WebGL is unavailable, reduced-motion is set, or the model fails to load,
 * the hook reports "fallback" and the static `LandingHeroFallback` shows
 * instead. The hero exposes no public API and captures no input.
 */

import { useRef } from "react";
import { cn } from "@/lib/cn";
import { useAsciiDna } from "./useAsciiDna";
import { LandingHeroFallback } from "./LandingHeroFallback";

export function LandingHero({ className }: { className?: string }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const status = useAsciiDna(stageRef);
  const showFallback = status === "fallback";

  return (
    <div aria-hidden="true" style={{ pointerEvents: "none" }} className={cn("hf-dna", className)}>
      <div className="hf-dna__inner">
        {showFallback ? (
          <LandingHeroFallback />
        ) : (
          <div
            ref={stageRef}
            data-landing-hero="stage"
            data-dna-ready={status === "ready" ? "true" : undefined}
            className="hf-dna__stage"
          />
        )}
      </div>
    </div>
  );
}
