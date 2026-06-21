"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";
import { cn } from "@/lib/cn";

// Leading status dot: a small disc whose color comes from the matching status
// token (re-resolves under .dark). Replaces the lucide glyphs so the toast
// matches the ink-surface mockup (dark panel, paper text, one colored dot).
function StatusDot({ className }: { className: string }) {
  return (
    <span aria-hidden="true" className={cn("block size-[7px] shrink-0 rounded-full", className)} />
  );
}

const Toaster = ({ ...props }: ToasterProps) => {
  // Dark mode here is class-based (the `.dark` element via the @custom-variant);
  // there is no next-themes provider. The ink-surface colors are driven by the
  // hf tokens below, which re-resolve under `.dark`, so the toaster follows the
  // app theme. Entrance/exit animation is left to sonner and is collapsed for
  // users who prefer reduced motion by the global guard in index.css.
  return (
    <Sonner
      className="toaster group"
      icons={{
        success: <StatusDot className="bg-hf-success" />,
        info: <StatusDot className="bg-hf-info" />,
        warning: <StatusDot className="bg-hf-warning" />,
        error: <StatusDot className="bg-hf-danger" />,
        loading: (
          <span
            aria-hidden="true"
            className="bg-hf-bg block size-[7px] shrink-0 animate-pulse rounded-full"
          />
        ),
      }}
      toastOptions={{
        // Remove sonner's default chrome so the ink panel is the only surface.
        unstyled: true,
        classNames: {
          // Ink panel + paper text (both flip under .dark), overlay-tier shadow,
          // softened radius. Matches the toast spec: ink surface, status dot.
          toast: cn(
            "flex w-full items-center gap-[11px] rounded-md px-4 py-3",
            "bg-hf-fg-1 text-hf-bg shadow-3",
            "text-sm font-sans",
          ),
          title: "font-medium text-hf-bg",
          description: "text-hf-bg/70",
          icon: "flex items-center justify-center",
          actionButton: cn("rounded-sm bg-hf-bg px-2 py-1 text-xs font-medium text-hf-fg-1"),
          cancelButton: cn("rounded-sm px-2 py-1 text-xs font-medium text-hf-bg/70"),
          closeButton: "text-hf-bg/70",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
