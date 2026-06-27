import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/cn";

const buttonVariants = cva(
  // Base — shared across all non-glass variants. Keeps the keyboard-only focus ring
  // (focus-visible:ring-[3px]) for soft, accessible keyboard navigation.
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
        // NOTE: every hf variant (primary/secondary/ghost/danger) is rendered
        // by the Button component through the layered .hf-glass path with a
        // per-variant tint class (hf-btn--{variant}); see the glass branches
        // below. These cva strings are the legacy non-glass fallback kept ONLY
        // for the standalone `buttonVariants()` helper / type-compat — the
        // Button component itself no longer applies them to hf variants.
        /** (legacy fallback) ink-leaning pill — glass-rendered as the CTA. */
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

        /** Warning text + optional soft fill on hover (out-of-date / re-run). */
        warning:
          "bg-transparent text-hf-warning rounded-[var(--radius-md)] border border-[color-mix(in_srgb,var(--hf-warning),transparent_60%)] hover:bg-hf-warning-soft active:translate-y-px",
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
// from index.css so they pick up all tier/fallback/refraction rules.
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

// Shared glass-action pill classes — ONE home for both the asChild anchor path
// and the plain <button> path so the two can't drift. Built directly (not via
// buttonVariants) because the size variants inject a fixed height (h-9) that,
// with .hf-glass overflow:hidden, would clip the padding-driven pill. `!` on the
// radius: the unlayered .hf-glass rule (--radius-xl) would otherwise outrank the
// utility and leave a rounded rect, not a pill.
const GLASS_PILL_BASE = cn(
  "hf-glass hf-glass--overlay inline-flex",
  "cursor-pointer rounded-[var(--radius-pill)]! border-0 p-0",
  "hover:-translate-y-0.5 active:translate-y-px",
  "outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
  "disabled:pointer-events-none disabled:opacity-45",
);

// Label layout for the landing-CTA glass pill (mockup .pill__label: 16/18/16/28
// padding, 24px gap, 16px medium). Reserved for the Hero CTA (`glass-action`).
const GLASS_PILL_LABEL =
  "inline-flex items-center gap-[24px] py-[16px] pr-[18px] pl-[28px] text-[16px] font-medium";

// Size-keyed label geometry for non-icon glass buttons. The glass pill is
// padding-driven (height comes from padding, not a fixed `h-*`, because
// .hf-glass clips with overflow:hidden), so each size scales its own
// padding/gap/text — mirroring the pre-glass shadcn size scale (sm < default <
// lg) so glass buttons feel consistent with it. `default` matches the mockup
// in-form .btn (11px/22px padding, 9px gap, ~0.86rem text); `sm` is the compact
// in-form pill ("Clear", dialog "Cancel"); `lg` is a roomier action pill that
// still stays below the landing CTA. The landing CTA keeps GLASS_PILL_LABEL.
const GLASS_PILL_BY_SIZE = {
  sm: "inline-flex items-center gap-[8px] py-[7px] px-[16px] text-sm font-medium",
  default: "inline-flex items-center gap-[9px] py-[11px] px-[22px] text-sm font-medium",
  lg: "inline-flex items-center gap-[14px] py-[14px] px-[28px] text-[15px] font-medium",
} as const;

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type ButtonVariant = NonNullable<VariantProps<typeof buttonVariants>["variant"]>;
type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>["size"]>;

// Resolve the non-icon glass label geometry from the size prop. The landing CTA
// (`glass-action`) keeps the large GLASS_PILL_LABEL regardless of size so the
// Hero pill is unchanged; every other glass variant scales by size (sm/lg map
// to their own geometry; everything else, incl. an unset size, is `default`).
function glassLabelClass(variant: string, size: ButtonSize | null | undefined): string {
  if (variant === "glass-action") return GLASS_PILL_LABEL;
  if (size === "sm") return GLASS_PILL_BY_SIZE.sm;
  if (size === "lg") return GLASS_PILL_BY_SIZE.lg;
  return GLASS_PILL_BY_SIZE.default;
}

// Glass label ink. Every glass variant uses the neutral foreground EXCEPT
// danger, which keeps destructive (red) color semantics even as a glass pill —
// the translucent tint alone is too subtle to read as "this deletes things".
function glassTextClass(variant: string): string {
  if (variant === "danger") return "text-hf-danger";
  if (variant === "warning") return "text-hf-warning";
  return "text-hf-fg-1";
}

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
  // All hf design-system variants render the layered .hf-glass recipe. Each
  // carries a per-variant tint class (hf-btn--{variant}) wired in index.css so
  // the CTA hierarchy is primary > secondary > ghost > danger. glass-action is
  // the bare overlay pill (no per-variant tint). The shadcn-original variants
  // (default/destructive/outline/link) stay on the non-glass cva path.
  const HF_GLASS_VARIANTS = [
    "primary",
    "secondary",
    "ghost",
    "danger",
    "warning",
    "glass-action",
  ] as const;
  // `variant` may be null per VariantProps; the destructure default only covers
  // undefined, so coalesce before the membership/tint checks.
  const resolvedVariant = variant ?? "default";
  const isGlass = (HF_GLASS_VARIANTS as readonly string[]).includes(resolvedVariant);
  const tintClass = resolvedVariant === "glass-action" ? "" : `hf-btn--${resolvedVariant}`;

  if (asChild) {
    // Glass-action + asChild: render the consumer's element (e.g. a router
    // <Link> -> <a>) AS the glass surface, injecting the same canonical
    // .hf-glass__* layers used by the non-asChild path and GlassSurface. This
    // lets a single anchor be the CTA pill — no <a> nested inside a <button>,
    // and no duplicated glass markup at the call site.
    if (isGlass && React.isValidElement(children)) {
      const child = children as React.ReactElement<{
        children?: React.ReactNode;
      }>;
      return (
        <Slot.Root
          data-slot="button"
          data-variant={variant}
          data-size={size}
          className={cn(GLASS_PILL_BASE, tintClass, className)}
          {...props}
        >
          {React.cloneElement(
            child,
            undefined,
            <>
              <GlassLayers />
              <span
                className={cn(
                  "hf-glass__content",
                  glassTextClass(resolvedVariant),
                  glassLabelClass(resolvedVariant, size),
                )}
              >
                {child.props.children}
              </span>
            </>,
          )}
        </Slot.Root>
      );
    }

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
    // Icon-only glass control (e.g. the theme switcher): a fixed square that
    // reads as a circle (square + pill radius), icon centred, no label padding.
    // Non-icon = a size-scaled glass label pill (glass-action stays the large
    // landing CTA; everything else scales sm/default/lg).
    const iconSizeClass =
      size === "icon"
        ? "size-9"
        : size === "icon-xs"
          ? "size-6"
          : size === "icon-sm"
            ? "size-8"
            : size === "icon-lg"
              ? "size-10"
              : null;
    const isIcon = iconSizeClass !== null;
    return (
      <button
        data-slot="button"
        data-variant={variant}
        data-size={size}
        className={cn(GLASS_PILL_BASE, tintClass, iconSizeClass, className)}
        {...props}
      >
        <GlassLayers />
        {/* Layer 3: content slot — uses .hf-glass__content for z-index:3 */}
        <span
          className={cn(
            "hf-glass__content",
            glassTextClass(resolvedVariant),
            isIcon ? "grid size-full place-items-center" : glassLabelClass(resolvedVariant, size),
          )}
        >
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
