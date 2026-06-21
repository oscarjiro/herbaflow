import * as React from "react";
import { ExternalLinkIcon, InfoIcon } from "lucide-react";

import { cn } from "@/lib/cn";

/**
 * Liquid-glass data-table primitives — SOLID look (not glass).
 *
 * These stay dumb styled primitives: all sort / pagination STATE lives in
 * DataTable (TanStack). data-slot attributes are preserved because DataTable
 * (and its tests) key off them. Headers are uppercase + tracked per the
 * mockup (thead th: uppercase, letter-spacing 0.04em, --hf-fg-3). Hover uses
 * the hf surface-2 token instead of shadcn bg-muted. Numeric columns opt into
 * tabular-nums via className passthrough.
 */

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className="relative w-full overflow-x-auto">
      <table
        data-slot="table"
        className={cn("w-full caption-bottom border-collapse text-sm", className)}
        {...props}
      />
    </div>
  );
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("[&_tr]:border-hf-border [&_tr]:border-b", className)}
      {...props}
    />
  );
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  );
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "bg-hf-surface-2 text-hf-fg-2 border-hf-border border-t font-medium [&>tr]:last:border-b-0",
        className,
      )}
      {...props}
    />
  );
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-hf-border hover:bg-hf-surface-2 has-aria-expanded:bg-hf-surface-2 data-[state=selected]:bg-hf-surface-2 border-b transition-colors",
        className,
      )}
      {...props}
    />
  );
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        // Uppercase + tracked editorial header per mockup (thead th).
        "text-hf-fg-3 h-10 px-4 text-left align-middle text-xs font-medium tracking-[0.04em] whitespace-nowrap uppercase",
        "[&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
        className,
      )}
      {...props}
    />
  );
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "text-hf-fg-1 px-4 py-3 align-middle whitespace-nowrap",
        "[&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
        className,
      )}
      {...props}
    />
  );
}

function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("text-hf-fg-3 mt-4 text-sm", className)}
      {...props}
    />
  );
}

/**
 * InfoHint — reusable per-column info (i) affordance.
 *
 * A small, accessible icon button that surfaces a short explanation of a
 * column. The shell ships the styled building block; columns wire it in a
 * later spec. The `label` is exposed both as the accessible name and the
 * native title tooltip.
 */
function InfoHint({
  label,
  className,
  ...props
}: { label: string } & Omit<React.ComponentProps<"button">, "aria-label">) {
  return (
    <button
      type="button"
      data-slot="table-info-hint"
      aria-label={label}
      title={label}
      className={cn(
        "text-hf-fg-3 hover:text-hf-fg-1 inline-flex size-4 shrink-0 items-center justify-center rounded-[var(--radius-sm)] align-middle transition-colors",
        "outline-none focus-visible:ring-[2px] focus-visible:ring-[color-mix(in_srgb,var(--hf-fg-1),transparent_55%)]",
        className,
      )}
      {...props}
    >
      <InfoIcon className="size-[14px]" aria-hidden="true" />
    </button>
  );
}

/**
 * ExternalLinkCell — reusable styled external link for accession cells.
 *
 * Renders an underline-on-hover ink link with a trailing external-link icon,
 * opening in a new tab with safe rel. The shell ships the styled building
 * block; accession columns wire it in a later spec.
 */
function ExternalLinkCell({
  href,
  children,
  className,
  ...props
}: React.ComponentProps<"a"> & { href: string }) {
  return (
    <a
      data-slot="table-external-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "text-hf-fg-1 inline-flex items-center gap-1 underline-offset-2 transition-colors hover:underline",
        className,
      )}
      {...props}
    >
      {children}
      <ExternalLinkIcon className="text-hf-fg-3 size-[13px] shrink-0" aria-hidden="true" />
    </a>
  );
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
  InfoHint,
  ExternalLinkCell,
};
