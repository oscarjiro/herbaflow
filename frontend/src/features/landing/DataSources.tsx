import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/cn";

// Public databases the pipeline draws from. Each chip links to the database it cites,
// so every record can be traced back to its source.
const SOURCES = [
  { label: "KNApSAcK", url: "https://www.knapsackfamily.com/KNApSAcK/" },
  { label: "ChEMBL", url: "https://www.ebi.ac.uk/chembl/" },
  { label: "PubChem BioAssay", url: "https://pubchem.ncbi.nlm.nih.gov/" },
  { label: "Open Targets", url: "https://platform.opentargets.org/" },
  { label: "STRING", url: "https://string-db.org/" },
  { label: "g:Profiler", url: "https://biit.cs.ut.ee/gprofiler/" },
] as const;

export function DataSources({ className }: { className?: string }) {
  return (
    <section
      className={cn("py-24 text-center md:py-32", className)}
      aria-labelledby="data-sources-heading"
    >
      <h2 id="data-sources-heading" className="text-hf-fg-3 text-[11px] tracking-[0.3em] uppercase">
        Built on public, citable data
      </h2>
      <ul className="mt-8 flex list-none flex-wrap items-center justify-center gap-3 p-0">
        {SOURCES.map(({ label, url }) => (
          <li key={label}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="border-hf-border text-hf-fg-2 hover:text-hf-fg-1 hover:border-hf-border-strong inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors"
            >
              {label}
              <ExternalLink
                size={13}
                strokeWidth={1.5}
                className="opacity-[0.55]"
                aria-hidden="true"
              />
            </a>
          </li>
        ))}
      </ul>
      <p className="text-hf-fg-3 mt-8 text-sm">
        Every record links back to the database it came from.
      </p>
    </section>
  );
}
