# Per-stage results

One CSV per pipeline stage (always present; an empty stage carries a `# note` line so you know
it ran but produced no rows). PNG charts accompany the stages that generate one.

---

## Stage 1: Compound resolution

**`stage1_compounds.csv`**

The compounds that entered the pipeline after resolving your plant selection (or manual compound
list) through PubChem.

| Column | Meaning |
|---|---|
| `compound` | Canonical compound name. |
| `inchikey` | IUPAC InChIKey (stable structural identifier, 27 characters). |
| `smiles` | SMILES string encoding the compound's 2-D chemical structure. |

---

## Stage 2: ADME / drug-likeness filter

**`stage2_adme.csv`**

All compounds that were evaluated for drug-likeness. Both passing and filtered compounds are
included; the `passed` column tells you which bucket each compound fell into.

| Column | Meaning |
|---|---|
| `compound_id` | Internal compound identifier. |
| `canonical_name` | Canonical compound name. |
| `passed` | `true` if the compound passed the ADME gate; `false` if it was filtered out. |
| `descriptor_source` | Where the molecular descriptors came from (e.g. `pubchem`, `rdkit`). |
| `molecular_weight` | Molecular weight in Da. |
| `logp` | Calculated partition coefficient (lipophilicity). |
| `hbond_donors` | Number of hydrogen-bond donors. |
| `hbond_acceptors` | Number of hydrogen-bond acceptors. |
| `tpsa` | Topological polar surface area (Å²). |
| `rotatable_bonds` | Number of rotatable bonds (flexibility indicator). |
| `qed_score` | Quantitative Estimate of Drug-likeness (0 to 1; higher = more drug-like). |
| `np_likeness_score` | Natural-product likeness score. |
| `num_ro5_violations` | Number of Lipinski Rule-of-Five violations. |
| `is_pains_positive` | `True` if the compound triggered a PAINS (pan-assay interference) alert. |
| `source_url` | PubChem compound page URL. |
| `reason` | Why a compound was filtered (blank if it passed). |

---

## Stage 3: Compound to target identification

**`stage3_compound_targets.csv`**

Protein targets with measured or predicted bioactivity against the ADME-passing compounds.
Evidence comes from ChEMBL (measured bioactivities) and PubChem BioAssay (active assay
outcomes).

| Column | Meaning |
|---|---|
| `gene_symbol` | HGNC gene symbol of the target protein. |
| `uniprot_accession` | UniProt accession of the target protein. |
| `prediction_method` | Evidence source: `chembl_bioactivity` or `pubchem_bioassay`. |
| `source_url` | UniProt entry page for the target. |

---

## Stage 4: Disease to target collection

**`stage4_disease_targets.csv`**

Targets associated with the disease of interest, sourced from the Open Targets database
(pre-loaded associations; not a live call at analysis time).

| Column | Meaning |
|---|---|
| `gene_symbol` | HGNC gene symbol. |
| `uniprot_accession` | UniProt accession. |
| `opentargets_score` | Open Targets association score (0 to 1; higher = stronger evidence). |
| `source_url` | UniProt entry page for the target. |

---

## Stage 5: Target overlap (mechanistic core)

**`stage5_overlap.csv`** · **`stage5_venn.png`**

The intersection of Stage 3 and Stage 4 targets: the proteins that are both active against
the plant compounds and implicated in the disease. This is the mechanistic core of the analysis.

`stage5_venn.png` shows a Venn diagram of the two sets with the overlap highlighted.

| Column | Meaning |
|---|---|
| `gene_symbol` | HGNC gene symbol. |
| `uniprot_accession` | UniProt accession. |
| `opentargets_score` | Open Targets association score carried forward from Stage 4. |

---

## Stage 6: Protein-protein interaction (PPI) network

**`stage6_ppi_edges.csv`** · **`stage6_ppi_network.png`**

STRING PPI network built over the overlap targets. The per-stage CSV is the edge list
(node metadata ships in the network bundle's `ppi-nodes.csv`).

`stage6_ppi_network.png` shows the network with hub proteins highlighted.

| Column | Meaning |
|---|---|
| `source` | Gene symbol of one interaction partner. |
| `target` | Gene symbol of the other interaction partner. |
| `confidence` | STRING combined interaction score (0 to 1). |

---

## Stage 7: Hub gene ranking

**`stage7_hubs.csv`** · **`stage7_hub_bar.png`**

Targets ranked by their centrality in the PPI network using the Matthews Correlation Coefficient
(MCC) of the node's local neighbourhood. Higher MCC = more topologically central.

`stage7_hub_bar.png` shows a bar chart of the top hub genes by MCC score.

| Column | Meaning |
|---|---|
| `rank` | Hub rank (1 = highest MCC score). |
| `gene_symbol` | HGNC gene symbol. |
| `uniprot_accession` | UniProt accession. |
| `degree` | Normalised degree centrality (fraction of possible connections). |
| `betweenness` | Normalised betweenness centrality (fraction of shortest paths via this node). |
| `closeness` | Normalised closeness centrality. |
| `eigenvector` | Normalised eigenvector centrality (influence weighted by neighbour importance). |
| `mcc` | MCC score used for ranking (integer; higher = more central). |

---

## Stage 8: Functional enrichment

**`stage8_enrichment.csv`** · **`stage8_enrichment_<CATEGORY>.png`**

Functional enrichment of the overlap targets against the compound-target universe (custom
background) using g:Profiler (over-representation analysis). Sources include Gene Ontology
(GO:BP / GO:MF / GO:CC), KEGG, Reactome, and WikiPathways.

This is **one combined** `stage8_enrichment.csv` containing results from all sources; the
`source` column distinguishes them (e.g. `GO:BP`, `KEGG`, `REAC`, `WP`). Separate PNG charts
are generated per category: for example `stage8_enrichment_GO:BP.png`, `stage8_enrichment_KEGG.png`,
`stage8_enrichment_REAC.png`, `stage8_enrichment_WP.png` (a category PNG is omitted if it has
no significant terms).

| Column | Meaning |
|---|---|
| `term_id` | Pathway or ontology term identifier (e.g. `GO:0045944`, `KEGG:04151`). |
| `name` | Human-readable term name. |
| `source` | Database source: `GO:BP`, `GO:MF`, `GO:CC`, `KEGG`, `REAC`, or `WP`. |
| `p_value` | BH-corrected enrichment p-value (full precision). |
| `intersection_size` | Number of overlap genes annotated to this term. |
| `intersection_genes` | Semicolon-separated list of those gene symbols. |
| `source_url` | Link to the term's page in its source database. |
