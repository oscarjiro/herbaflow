export default function AboutPage() {
  return (
    <div className="py-12 px-6">
      <div className="max-w-3xl mx-auto flex flex-col gap-8">
        <h1 className="font-display text-4xl text-hf-fg1">About Herbaflow</h1>

        {/* Project */}
        <div className="bg-hf-surface border border-hf-border rounded-lg p-6 flex flex-col gap-3">
          <h2 className="font-sans font-semibold text-lg text-hf-fg1">Project</h2>
          <p className="font-sans text-sm text-hf-fg2 leading-relaxed">
            Herbaflow is a network pharmacology analysis tool developed as a thesis project. It
            focuses on Indonesian medicinal plants catalogued in the KNApSAcK database, providing
            a structured pipeline for mapping plant-compound-disease-target relationships. The
            platform supports reproducible, stage-by-stage pharmacological network construction
            from raw plant selections through to pathway enrichment.
          </p>
        </div>

        {/* Methodology */}
        <div className="bg-hf-surface border border-hf-border rounded-lg p-6 flex flex-col gap-3">
          <h2 className="font-sans font-semibold text-lg text-hf-fg1">Methodology</h2>
          <p className="font-sans text-sm text-hf-fg2 leading-relaxed mb-2">
            Analysis proceeds through eight sequential stages:
          </p>
          <ol className="font-sans text-sm text-hf-fg2 leading-relaxed list-none flex flex-col gap-2">
            {[
              ['1', 'Compound Selection', 'Retrieve active compounds for selected medicinal plants from KNApSAcK.'],
              ['2', 'ADME Screening', 'Filter compounds by drug-likeness criteria using Lipinski and ADME parameters.'],
              ['3', 'Target Identification', 'Predict protein targets for screened compounds via reverse docking or target databases.'],
              ['4', 'Disease Target Mapping', 'Cross-reference compound targets with known disease-associated targets.'],
              ['5', 'Target Overlap', 'Compute intersections between plant-derived compound targets and disease targets.'],
              ['6', 'PPI Network Construction', 'Build protein-protein interaction networks from overlapping targets.'],
              ['7', 'Hub Gene Analysis', 'Identify hub genes by topological metrics (degree, betweenness, closeness centrality).'],
              ['8', 'Pathway Enrichment', 'Perform GO and KEGG pathway enrichment on hub genes to interpret biological significance.'],
            ].map(([num, title, desc]) => (
              <li key={num} className="flex gap-3">
                <span className="font-display text-hf-fg3 text-base w-5 shrink-0">{num}.</span>
                <span>
                  <span className="text-hf-fg1 font-medium">{title}</span>
                  {' — '}
                  <span className="text-hf-fg3">{desc}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>

        {/* Author */}
        <div className="bg-hf-surface border border-hf-border rounded-lg p-6 flex flex-col gap-3">
          <h2 className="font-sans font-semibold text-lg text-hf-fg1">Author</h2>
          <p className="font-sans text-sm text-hf-fg2 leading-relaxed">
            Herbaflow was built by <span className="text-hf-fg1 font-medium">Oscar Jiro</span> as
            part of an undergraduate thesis in pharmacy / pharmaceutical sciences. The project
            demonstrates applied network pharmacology methods for studying Indonesian traditional
            medicine at a molecular level.
          </p>
        </div>

        {/* User Manual */}
        <div className="bg-hf-surface border border-hf-border rounded-lg p-6 flex flex-col gap-3">
          <h2 className="font-sans font-semibold text-lg text-hf-fg1">User Manual</h2>
          <p className="font-sans text-sm text-hf-fg3 leading-relaxed">
            A detailed user manual covering pipeline configuration, guided and auto analysis
            modes, and result interpretation is coming soon.
          </p>
        </div>
      </div>
    </div>
  )
}
