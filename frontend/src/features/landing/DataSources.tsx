import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/cn";
import { GlassSurface } from "@/components/ui/GlassSurface";

// Public databases the pipeline draws from. Each chip links to the database it cites,
// so every record can be traced back to its source.
const SOURCES = [
  { label: "KNApSAcK", url: "https://www.knapsackfamily.com/KNApSAcK/" },
  { label: "ChEMBL", url: "https://www.ebi.ac.uk/chembl/" },
  { label: "PubChem", url: "https://pubchem.ncbi.nlm.nih.gov/" },
  { label: "Open Targets", url: "https://platform.opentargets.org/" },
  { label: "STRING", url: "https://string-db.org/" },
  { label: "g:Profiler", url: "https://biit.cs.ut.ee/gprofiler/" },
] as const;

export function DataSources({ className }: { className?: string }) {
  return (
    <section
      className={cn("border-hf-border border-t py-16 text-center", className)}
      aria-labelledby="data-sources-heading"
    >
      <h2 id="data-sources-heading" className="text-hf-fg-3 text-[11px] tracking-[0.3em] uppercase">
        Built on public, citable data
      </h2>
      <ul className="mt-6 flex list-none flex-wrap items-center justify-center gap-4 p-0">
        {SOURCES.map(({ label, url }) => (
          <li key={label}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="focus-visible:ring-ring/50 group inline-block rounded-[var(--radius-pill)] transition-transform outline-none hover:-translate-y-0.5 focus-visible:ring-[3px]"
            >
              <GlassSurface tier="chrome" className="rounded-[var(--radius-pill)]">
                <span className="text-hf-fg-2 group-hover:text-hf-fg-1 inline-flex items-center gap-2 px-4 py-2 text-sm transition-colors">
                  {label}
                  <ExternalLink
                    size={13}
                    strokeWidth={1.5}
                    className="opacity-[0.55]"
                    aria-hidden="true"
                  />
                </span>
              </GlassSurface>
            </a>
          </li>
        ))}
      </ul>
      <p className="text-hf-fg-3 mt-6 text-sm">
        Every record links back to the database it came from.
      </p>
    </section>
  );
}
