import { cn } from "@/lib/cn";
import { ExternalLink } from "./ExternalLink";

// ---------------------------------------------------------------------------
// SourceChip — monospace source-name pill; optionally links to a URL
// ---------------------------------------------------------------------------

interface SourceChipProps {
  name: string;
  url?: string | null;
  className?: string;
}

const pillClass =
  "font-mono text-[0.62rem] uppercase tracking-[0.06em] px-2 py-0.5 rounded-full border border-hf-border-strong text-hf-fg-3 inline-block";

function SourceChip({ name, url, className }: SourceChipProps) {
  if (url) {
    // Render the entire pill as a link; override ExternalLink's underline so the
    // pill border carries the affordance instead.
    return (
      <ExternalLink
        href={url}
        className={cn(pillClass, "no-underline hover:no-underline", className)}
      >
        {name}
      </ExternalLink>
    );
  }

  return <span className={cn(pillClass, className)}>{name}</span>;
}

export { SourceChip };
export type { SourceChipProps };
