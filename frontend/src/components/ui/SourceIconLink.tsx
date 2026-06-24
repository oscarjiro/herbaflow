import { ExternalLink } from "lucide-react";

import { cn } from "@/lib/cn";

type SourceIconLinkProps = {
  href: string;
  label: string;
  className?: string;
  stopPropagation?: boolean;
};

function SourceIconLink({ href, label, className, stopPropagation }: SourceIconLinkProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      aria-label={label}
      title={label}
      onClick={stopPropagation ? (event) => event.stopPropagation() : undefined}
      className={cn(
        "text-hf-fg-3 hover:text-hf-fg-1 focus-visible:ring-ring/50 inline-flex size-5 shrink-0 items-center justify-center rounded-sm transition-colors focus-visible:ring-[2px] focus-visible:outline-none",
        className,
      )}
    >
      <ExternalLink aria-hidden="true" className="size-3.5" />
    </a>
  );
}

export { SourceIconLink };
