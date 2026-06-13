const STAGE_SOURCES: Record<number, string[]> = {
  1: ["KNApSAcK (plant–compound)", "PubChem (manual enrichment)"],
  2: ["RDKit (descriptors, PAINS)"],
  3: ["ChEMBL", "PubChem BioAssay", "UniProt"],
  4: ["Open Targets (ETL-seeded disease–target associations)", "UniProt"],
  5: [
    "Overlap of Stage 3 ∩ Stage 4 (target_id)",
    "Jaccard + one-sided hypergeometric (N=20,000, α=0.05)",
  ],
  6: ["STRING (protein–protein interactions)", "Human only (species 9606); functional or physical"],
  7: ["networkx (centrality analysis)", "STRING PPI network (undirected)"],
  8: ["g:Profiler (GO + KEGG enrichment)"],
};

// When an entity stage is user-provided, only the manual-resolution source actually ran — the
// computed-mode external sources (KNApSAcK / ChEMBL / PubChem BioAssay / Open Targets) did NOT.
const USER_PROVIDED_SOURCES: Record<number, string[]> = {
  1: ["PubChem (manual compound resolution)"],
  3: ["UniProt (manual target resolution)"],
  4: ["UniProt (manual target resolution)"],
};

export function StageDataSources({ stage, userProvided = false }: { stage: number; userProvided?: boolean }) {
  const sources = (userProvided && USER_PROVIDED_SOURCES[stage]) ? USER_PROVIDED_SOURCES[stage] : STAGE_SOURCES[stage];
  if (!sources) return null;
  return (
    <div className="stage-data-sources hf-muted" aria-label="Data sources">
      <span className="stage-data-sources__label">Data sources</span>
      <ul>
        {sources.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </div>
  );
}
