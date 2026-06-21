/**
 * AiLoader — a glossy spinning orb with a sage→terracotta accent glow and a
 * status label whose letters pulse in sequence. Ported verbatim from the
 * mockup (primitives-fixes.html): the orb's spin keyframe shifts its inset
 * box-shadow from a sage glow to a terracotta glow as it rotates (the one
 * decorative use of the data-viz accents), and the label letters stagger their
 * pulse via per-letter animation-delay.
 *
 * Keyframes (`hf-orb-spin`, `hf-letter-pulse`) and the static gloss base
 * (`.hf-ai-orb`) live in src/index.css so the colour stops resolve from the
 * `--hf-*` tokens (and re-resolve under `.dark`). No raw hex here.
 *
 * Reduced motion: the orb stops spinning and the label stops pulsing. Per the
 * design-system rule we do not rely on the global CSS guard alone — the
 * component conditionally OMITS the spin/pulse animation classes and renders a
 * single static state (glossy sage orb, full-opacity label). Detection reuses
 * `useReducedMotion` from motion/react (same as StatefulButton / Switch).
 *
 * Accessibility:
 *  - the orb is decorative (`aria-hidden`)
 *  - the label is an `aria-live="polite"` status region so the current phrase
 *    is announced; the per-letter spans are hidden from the accessibility tree
 *    so the phrase reads as one word.
 */

import { useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";
import { cn } from "@/lib/cn";

interface AiLoaderProps {
  /** Status phrases to cycle through (plain scientific English). */
  phrases?: string[];
  /** Orb diameter in px. Mockup defaults: 56 (default), 38 (small). */
  size?: number;
  /** How long (ms) each phrase shows before advancing. Default 2600. */
  phraseDuration?: number;
  className?: string;
}

/** Plain-English, jargon-free defaults. No internal stage names, no em dashes. */
const DEFAULT_PHRASES = ["Analyzing", "Building network", "Scoring targets", "Finishing up"];

export function AiLoader({
  phrases = DEFAULT_PHRASES,
  size = 56,
  phraseDuration = 2600,
  className,
}: AiLoaderProps) {
  const shouldReduceMotion = useReducedMotion();
  const [index, setIndex] = useState(0);

  // Cycle through the phrases. Skipped entirely under reduced motion so the
  // label stays on a single static phrase.
  useEffect(() => {
    if (shouldReduceMotion || phrases.length <= 1) return;
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % phrases.length);
    }, phraseDuration);
    return () => clearInterval(id);
  }, [shouldReduceMotion, phrases.length, phraseDuration]);

  const phrase = phrases[index % phrases.length] ?? phrases[0] ?? "";
  // Trailing ellipsis character, pulsed last (matches the mockup's …).
  const letters = [...phrase, "…"];

  return (
    <div className={cn("inline-flex flex-col items-center gap-3.5", className)} data-ai-loader="">
      {/* Decorative glossy orb. The gradient gloss comes from the .hf-ai-orb
          base rule; the spin keyframe animates the inset box-shadow between the
          sage and terracotta glows. */}
      <span
        aria-hidden="true"
        data-ai-orb=""
        data-motion-reduced={shouldReduceMotion ? "true" : undefined}
        className={cn(
          "hf-ai-orb block shrink-0 rounded-[var(--radius-pill)]",
          !shouldReduceMotion && "animate-[hf-orb-spin_2s_linear_infinite]",
        )}
        style={{ width: size, height: size }}
      />

      {/* Status label — letters pulse in sequence. aria-live announces the
          phrase; the per-letter spans are aria-hidden so it reads as a word. */}
      <span
        role="status"
        aria-live="polite"
        aria-label={phrase}
        className="text-hf-fg-2 inline-flex [gap:0.5px] font-sans text-sm font-medium tracking-wide"
        style={{ fontSize: size <= 40 ? 12 : 13 }}
      >
        {letters.map((ch, n) => (
          <span
            key={`${index}-${n}`}
            aria-hidden="true"
            data-ai-letter=""
            className={cn(
              "inline-block",
              !shouldReduceMotion && "animate-[hf-letter-pulse_2.1s_infinite]",
            )}
            style={
              shouldReduceMotion
                ? undefined
                : { animationDelay: ch === "…" ? "1s" : `${n * 0.09}s` }
            }
          >
            {ch === " " ? " " : ch}
          </span>
        ))}
      </span>
    </div>
  );
}
