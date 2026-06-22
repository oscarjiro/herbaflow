import { useMatchRoute } from "@tanstack/react-router";

export function Footer() {
  const matchRoute = useMatchRoute();
  // The run page owns its own chrome — no global footer there.
  if (matchRoute({ to: "/analysis/$id" })) return null;

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
          © 2026 · Herbaflow · Oscar Jiro
        </div>
      </div>
    </footer>
  );
}
