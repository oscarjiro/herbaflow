import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { GlassSurface } from "@/components/ui/GlassSurface";

/** Outline glyph for a timeline node. Strokes follow currentColor so the icon
 *  inverts correctly on the ink-filled bookend nodes. */
function NodeIcon({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Data — verbatim from the landing page design spec §5
// ---------------------------------------------------------------------------

interface TimelineEntry {
  /** "Inputs" | "Step 01"…"Step 08" | "Handoff" */
  label: string;
  /** Display name of this step */
  name: string;
  /** One-line plain-science description */
  description: string;
  /** Source attribution line — null for steps with no source tag (Step 05, Step 08) */
  source: string | null;
  /** True for the Inputs and Export bookend rows */
  isBookend: boolean;
  /** Outline glyph rendered inside the rail node */
  icon: ReactNode;
}

const ENTRIES: TimelineEntry[] = [
  {
    label: "Inputs",
    name: "Plant and disease",
    description: "Choose the medicinal plant or plants to study and the disease to investigate.",
    source: "plant · disease",
    isBookend: true,
    icon: (
      <NodeIcon>
        <path d="M12 21V9" />
        <polyline points="7 14 12 9 17 14" />
        <path d="M5 3h14" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 01",
    name: "Compound selection",
    description: "Pull the bioactive compounds reported for your chosen plant.",
    source: "KNApSAcK",
    isBookend: false,
    icon: (
      <NodeIcon>
        <path d="M11 20A7 7 0 0 1 4 13c0-5 5-9 11-9 0 6-4 11-9 11" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 02",
    name: "Drug-likeness screening",
    description:
      "Filter for orally plausible molecules with Lipinski's rule of five and Veber's rules, keeping a natural-product exception.",
    source: "Lipinski RO5 · Veber",
    isBookend: false,
    icon: (
      <NodeIcon>
        <circle cx="9" cy="9" r="4" />
        <circle cx="16" cy="15" r="4" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 03",
    name: "Compound to targets",
    description:
      "Find the human proteins each compound is measured to act on. Bioactivity is taken from experiment, not predicted, unless you add predictions yourself.",
    source: "ChEMBL · PubChem",
    isBookend: false,
    icon: (
      <NodeIcon>
        <circle cx="6" cy="12" r="3" />
        <circle cx="18" cy="7" r="3" />
        <circle cx="18" cy="17" r="3" />
        <line x1="8.7" y1="10.8" x2="15.3" y2="8.2" />
        <line x1="8.7" y1="13.2" x2="15.3" y2="15.8" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 04",
    name: "Disease to targets",
    description:
      "Collect the human proteins associated with your disease, scored by strength of evidence.",
    source: "Open Targets",
    isBookend: false,
    icon: (
      <NodeIcon>
        <path d="M12 21s-7-4.35-7-10a7 7 0 0 1 14 0c0 5.65-7 10-7 10z" />
        <circle cx="12" cy="11" r="2.5" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 05",
    name: "Target overlap",
    description:
      "The proteins where compound reach and disease biology meet, drawn as a Venn diagram.",
    // Spec §5 explicitly: Step 05 has no source tag
    source: null,
    isBookend: false,
    icon: (
      <NodeIcon>
        <circle cx="9" cy="12" r="6" />
        <circle cx="15" cy="12" r="6" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 06",
    name: "Interaction network",
    description:
      "How those shared proteins interact, assembled from known associations at a confidence cutoff you choose.",
    source: "STRING",
    isBookend: false,
    icon: (
      <NodeIcon>
        <circle cx="12" cy="5" r="2" />
        <circle cx="5" cy="18" r="2" />
        <circle cx="19" cy="18" r="2" />
        <line x1="12" y1="7" x2="6" y2="16.3" />
        <line x1="12" y1="7" x2="18" y2="16.3" />
        <line x1="7" y1="18" x2="17" y2="18" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 07",
    name: "Hub genes",
    description:
      "The most central proteins in the network, ranked by maximal clique centrality, with four classical centrality measures reported alongside.",
    source: "MCC (CytoHubba)",
    isBookend: false,
    icon: (
      <NodeIcon>
        <circle cx="12" cy="12" r="2.5" />
        <circle cx="4" cy="6" r="1.5" />
        <circle cx="20" cy="6" r="1.5" />
        <circle cx="4" cy="18" r="1.5" />
        <circle cx="20" cy="18" r="1.5" />
        <line x1="5.3" y1="6.7" x2="10.2" y2="10.6" />
        <line x1="18.7" y1="6.7" x2="13.8" y2="10.6" />
        <line x1="5.3" y1="17.3" x2="10.2" y2="13.4" />
        <line x1="18.7" y1="17.3" x2="13.8" y2="13.4" />
      </NodeIcon>
    ),
  },
  {
    label: "Step 08",
    name: "Functional enrichment",
    // Spec §5: Step 08's tools live in its description, not a tag
    description:
      "The biological processes and pathways the network is built from, found with g:Profiler across GO and KEGG and corrected for multiple testing.",
    source: null,
    isBookend: false,
    icon: (
      <NodeIcon>
        <line x1="5" y1="20" x2="5" y2="13" />
        <line x1="11" y1="20" x2="11" y2="9" />
        <line x1="17" y1="20" x2="17" y2="5" />
      </NodeIcon>
    ),
  },
  {
    label: "Handoff",
    name: "Export",
    description:
      "A publishable figure set and Cytoscape-ready compound-target-pathway edge tables for downstream network analysis.",
    source: "figures · CSV",
    isBookend: true,
    icon: (
      <NodeIcon>
        <path d="M12 3v12" />
        <polyline points="7 10 12 15 17 10" />
        <path d="M5 21h14" />
      </NodeIcon>
    ),
  },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Circular node on the vertical rail. Bookend nodes use the accent fill. */
function TimelineNode({ isBookend, icon }: { isBookend: boolean; icon: ReactNode }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        // Base: circular node
        "grid flex-none place-items-center rounded-full",
        "h-11 w-11 border",
        // Non-bookend: ghost node with raised background
        // bg-[var(--hf-bg-raised)] — --color-hf-bg-raised is not in @theme inline,
        // so we use the CSS-variable arbitrary form instead of a utility alias.
        !isBookend && [
          "border-hf-border-strong text-hf-fg-1 bg-[var(--hf-bg-raised)]",
          "[box-shadow:0_2px_8px_-4px_rgba(26,26,26,0.2)]",
        ],
        // Bookend: ink-filled accent (--hf-accent = --hf-fg-1 in both themes)
        // bg-hf-fg-1 / text-hf-bg — both registered in @theme inline.
        isBookend && ["bg-hf-fg-1 border-hf-fg-1 text-hf-bg"],
      )}
    >
      {icon}
    </span>
  );
}

/** Single timeline row. */
function TimelineItem({ entry }: { entry: TimelineEntry }) {
  const isLast = entry.isBookend && entry.label === "Handoff";

  return (
    <li
      role="listitem"
      data-bookend={entry.isBookend ? "true" : undefined}
      className="grid gap-4 pb-8 last:pb-0"
      style={{ gridTemplateColumns: "60px 1fr" }}
    >
      {/* Left rail: node + connector line */}
      <div className="flex flex-col items-center">
        <TimelineNode isBookend={entry.isBookend} icon={entry.icon} />
        {!isLast && (
          <span
            aria-hidden="true"
            className="bg-hf-border-strong mt-1.5 mb-0 min-h-[18px] w-px flex-1"
          />
        )}
      </div>

      {/* Right: glass card */}
      <div className="self-start">
        <GlassSurface tier="raised" className="w-full">
          <div className="px-6 py-4">
            {/* Step label — sans, weight 600, letter-spaced, no mono */}
            <p className="text-hf-fg-3 text-[11px] font-semibold tracking-[0.16em] uppercase">
              {entry.label}
            </p>

            {/* Step name */}
            <p className="text-hf-fg-1 mt-[3px] mb-[5px] text-[18px] font-medium">{entry.name}</p>

            {/* Description */}
            <p className="text-hf-fg-2 max-w-[52ch] text-sm leading-[1.55]">{entry.description}</p>

            {/* Source attribution — only when spec provides one */}
            {entry.source !== null && (
              <p className="text-hf-fg-3 mt-[7px] text-xs">{entry.source}</p>
            )}
          </div>
        </GlassSurface>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// WorkflowTimeline
// ---------------------------------------------------------------------------

export function WorkflowTimeline() {
  return (
    <section className="pt-24 pb-16 text-center md:pt-32" aria-labelledby="workflow-heading">
      {/* Section heading */}
      <header className="mb-12 flex flex-col items-center gap-2">
        <span className="text-hf-fg-3 text-[11px] tracking-[0.3em] uppercase">Workflow system</span>
        <h2
          id="workflow-heading"
          className="font-display text-[clamp(2rem,4.2vw,3rem)] leading-[1.05] font-normal tracking-[-0.02em]"
        >
          Eight steps. <em>Every one inspectable.</em>
        </h2>
        <p className="text-hf-fg-2 mx-auto max-w-[60ch] text-base leading-[1.6]">
          Most tools turn a plant name into a network diagram and stop there. Herbaflow keeps you in
          the loop: at every step you can review, edit, or augment the intermediate set before it
          moves on. The provenance travels with the data.
        </p>
      </header>

      {/* Vertical timeline */}
      <ol className="m-0 mx-auto max-w-[760px] list-none p-0 text-left" aria-label="Workflow steps">
        {ENTRIES.map((entry) => (
          <TimelineItem key={entry.label} entry={entry} />
        ))}
      </ol>
    </section>
  );
}
