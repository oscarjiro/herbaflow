import { useMatchRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { toggleGlassPerfFallback } from "@/lib/glassSupport";

export function Footer() {
  const matchRoute = useMatchRoute();
  // The run page (and its per-stage children) owns its own chrome — no global footer there.
  // Fuzzy so the /$stage and /inputs child routes match too. The setup route (/analysis)
  // keeps the global footer: it lives in the standard site layout.
  if (matchRoute({ to: "/analysis/$id", fuzzy: true })) return null;

  return (
    <footer className="border-hf-border relative z-20 border-t">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-6 pt-16 pb-12 text-center">
        <span
          role="img"
          aria-label="Herbaflow"
          className="hf-logo text-hf-fg-2 block h-8 w-[128px]"
        />
        <p className="text-hf-fg-3 max-w-[46ch] text-sm leading-[1.6]">
          A solo thesis project in computational biology, built to make network pharmacology legible
          to researchers and students alike.
        </p>
        <div className="text-hf-fg-4 text-xs tracking-[0.04em]">
          © 2026 · Herbaflow ·{" "}
          {/* Hidden perf affordance: clicking the author name toggles the heavy
              Chromium-only liquid-glass refraction to the cheaper frosted
              fallback and back (persisted). Styled as plain text so it reads as
              a credit, not a control. */}
          <button
            type="button"
            onClick={() => {
              const fallback = toggleGlassPerfFallback();
              toast(fallback ? "Performance mode: liquid glass off" : "Liquid glass on");
            }}
            className="cursor-default appearance-none bg-transparent p-0 tracking-[inherit] text-inherit"
          >
            Oscar Jiro
          </button>
        </div>
      </div>
    </footer>
  );
}
