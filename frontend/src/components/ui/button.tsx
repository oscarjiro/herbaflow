import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/cn";

const buttonVariants = cva(
  // Base — shared across all non-glass variants. Focus ring kept from Task 4
  // (focus-visible:ring-[3px]) for keyboard-only soft ring.
  "inline-flex shrink-0 items-center justify-center gap-2 text-sm font-medium whitespace-nowrap transition-all outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-45 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // ── shadcn originals (kept for call-site compat) ──────────────────
        default: "bg-primary text-primary-foreground rounded-md hover:bg-primary/90",
        destructive:
          "bg-destructive text-white rounded-md hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:bg-destructive/60 dark:focus-visible:ring-destructive/40",
        outline:
          "border bg-background rounded-md shadow-xs hover:bg-accent hover:text-accent-foreground dark:border-input dark:bg-input/30 dark:hover:bg-input/50",
        link: "text-primary underline-offset-4 hover:underline",

        // ── hf design-system variants ─────────────────────────────────────
        /** Solid ink fill, pill radius — the primary CTA on pages/surfaces. */
        primary:
          "bg-hf-fg-1 text-hf-bg rounded-[var(--radius-pill)] px-5 py-2.5 hover:shadow-[0_8px_22px_-8px_color-mix(in_srgb,var(--hf-fg-1),transparent_35%)] active:translate-y-px",

        /**
         * Overlay-tier glass pill — reuses the `.hf-glass` / GlassSurface recipe.
         * The Button component handles this variant via a special render path that
         * injects the .hf-glass__refract/.hf-glass__tint/.hf-glass__shine layers.
         * This CVA entry is used only by the `buttonVariants()` helper for external use.
         */
        "glass-action":
          "hf-glass hf-glass--overlay rounded-[var(--radius-pill)] hover:-translate-y-0.5 active:translate-y-px outline-none",

        /** Surface fill + border — secondary / neutral actions. */
        secondary:
          "bg-hf-surface text-hf-fg-1 rounded-[var(--radius-md)] border border-hf-border-strong hover:bg-hf-surface-2 hover:border-hf-fg-3 active:translate-y-px",

        /** No fill — low-emphasis actions in toolbars / lists. */
        ghost:
          "bg-transparent text-hf-fg-2 rounded-[var(--radius-md)] hover:bg-hf-surface-2 hover:text-hf-fg-1 active:translate-y-px",

        /** Danger text + optional soft fill on hover. */
        danger:
          "bg-transparent text-hf-danger rounded-[var(--radius-md)] border border-[color-mix(in_srgb,var(--hf-danger),transparent_60%)] hover:bg-hf-danger-soft active:translate-y-px",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        xs: "h-6 gap-1 rounded-md px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1.5 rounded-md px-3 has-[>svg]:px-2.5",
        lg: "h-10 rounded-md px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-xs": "size-6 rounded-md [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

// ---------------------------------------------------------------------------
// Glass-action pill inner layers — uses the canonical .hf-glass__* CSS classes
// from Task 2 (index.css) so they pick up all tier/fallback/refraction rules.
// ---------------------------------------------------------------------------
function GlassLayers() {
  return (
    <>
      {/* Layer 0: refraction (frosted blur default; Chromium SVG displacement opt-in) */}
      <span aria-hidden="true" className="hf-glass__refract" />
      {/* Layer 1: tint wash */}
      <span aria-hidden="true" className="hf-glass__tint" />
      {/* Layer 2: rim-light / shine */}
      <span aria-hidden="true" className="hf-glass__shine" />
    </>
  );
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type ButtonVariant = NonNullable<VariantProps<typeof buttonVariants>["variant"]>;

interface ButtonProps
  extends Omit<React.ComponentProps<"button">, "ref">, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  children,
  ...props
}: ButtonProps) {
  const isGlass = variant === "glass-action";

  if (asChild) {
    return (
      <Slot.Root
        data-slot="button"
        data-variant={variant}
        data-size={size}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      >
        {children}
      </Slot.Root>
    );
  }

  if (isGlass) {
    return (
      <button
        data-slot="button"
        data-variant={variant}
        data-size={size}
        className={cn(
          // Glass pill base — absolute children need relative parent with overflow:hidden.
          // .hf-glass sets position:relative, overflow:hidden, isolation:isolate, box-shadow.
          // We override border-radius to pill, reset padding, set cursor.
          "hf-glass hf-glass--overlay",
          "cursor-pointer rounded-[var(--radius-pill)] border-0 p-0",
          "hover:-translate-y-0.5 active:translate-y-px",
          "outline-none",
          "focus-visible:ring-ring/50 focus-visible:ring-[3px]",
          "disabled:pointer-events-none disabled:opacity-45",
          className,
        )}
        {...props}
      >
        <GlassLayers />
        {/* Layer 3: content slot — uses .hf-glass__content for z-index:3 */}
        <span className="hf-glass__content text-hf-fg-1 inline-flex items-center gap-2 px-[22px] py-[11px] text-[13.5px] font-medium">
          {children}
        </span>
      </button>
    );
  }

  return (
    <button
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {children}
    </button>
  );
}

export { Button, buttonVariants };
export type { ButtonVariant };
