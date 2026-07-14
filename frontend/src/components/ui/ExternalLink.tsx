import * as React from "react";
import { ExternalLink as ExternalLinkIcon } from "lucide-react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// ExternalLink — inline link that opens in a new tab with an arrow icon
// ---------------------------------------------------------------------------

interface ExternalLinkProps {
  href: string;
  children: React.ReactNode;
  /** Accessible label override; falls back to the text content. */
  label?: string;
  className?: string;
  /** Stop click bubbling — use when the link sits inside another clickable row. */
  stopPropagation?: boolean;
}

function ExternalLink({ href, children, label, className, stopPropagation }: ExternalLinkProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={stopPropagation ? (event) => event.stopPropagation() : undefined}
      aria-label={label ? `${label} (opens in new tab)` : undefined}
      className={cn(
        "text-hf-fg-1 inline-flex items-center gap-[3px]",
        "decoration-hf-border-strong underline underline-offset-[3px]",
        "hover:decoration-hf-fg-1 transition-[text-decoration-color] duration-[var(--duration-1)]",
        className,
      )}
    >
      {children}
      <ExternalLinkIcon
        size={13}
        strokeWidth={1.5}
        className="text-hf-fg-3 shrink-0"
        aria-hidden="true"
      />
      {!label && <span className="sr-only"> (opens in new tab)</span>}
    </a>
  );
}

export { ExternalLink };
export type { ExternalLinkProps };
