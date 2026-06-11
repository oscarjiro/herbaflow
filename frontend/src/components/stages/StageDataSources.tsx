const STAGE_SOURCES: Record<number, string[]> = {
  1: ["KNApSAcK (plant–compound)", "PubChem (manual enrichment)"],
  2: ["RDKit (descriptors, PAINS)"],
  3: ["ChEMBL", "PubChem BioAssay", "UniProt"],
  4: ["Open Targets (ETL-seeded disease–target associations)"],
};

export function StageDataSources({ stage }: { stage: number }) {
  const sources = STAGE_SOURCES[stage];
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
