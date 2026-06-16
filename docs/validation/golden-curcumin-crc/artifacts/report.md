# Herbaflow Analysis: Colorectal Cancer, 2026-06-16

*Colorectal Cancer*

## About this analysis

- Scope: human proteins only (species 9606).
- These are computational predictions to guide research, not clinical conclusions.
- Enrichment is tested against the compound-target universe as background.

## Stage 1: Compounds

1 compounds supplied directly (user input).

**Data sources:** [PubChem (manual compound resolution)](https://pubchem.ncbi.nlm.nih.gov/)

Full table: `stages/stage1_compounds.csv`

## Stage 2: ADME filter

1 of 1 compounds passed drug-likeness filtering (Lipinski + Veber, natural-product exception applied), retaining the orally-plausible chemical space.

**Parameters**

| Parameter | Value | Description |
| --- | --- | --- |
| Max MW | 500 Da | Molecular weight ceiling (Da). Molecular size: larger molecules permeate membranes more poorly. |
| Max HBA | 10 | Hydrogen-bond acceptor ceiling (Σ N, O atoms). Adds a desolvation penalty. |
| Max HBD | 5 | Hydrogen-bond donor ceiling (Σ N-H, O-H). Each donor adds a desolvation penalty crossing membranes. |
| Max logP | 5 | Lipophilicity ceiling (logP, octanol-water partition). Balances solubility against membrane permeation. |
| Max TPSA | 140 Å² | Topological polar surface area ceiling (Å²). Polarity: high TPSA lowers absorption (Veber). |
| Skip Adme | No | Bypass ADME screening entirely: every compound passes, flagged not screened. |
| Apply Veber | Yes | Apply Veber's rules (rotatable bonds + TPSA) on top of Lipinski's four. |
| Max Violations | 1 | Number of the four Lipinski rules a compound may break and still pass (RO5 leniency). Veber is evaluated separately, not in this budget. |
| Apply NP Exception | Yes | Allow the natural-product-likeness exception to rescue rule-breaking compounds. Off = strict (no NP rescue). |
| Max Rotatable Bonds | 10 | Rotatable-bond ceiling. Molecular flexibility: too flexible lowers oral bioavailability (Veber). |
| NP Exception Threshold | 0.5 | Natural-product-likeness score (Ertl, approx [-5,+5]) at or above which a compound bypasses the rules, protecting genuine plant compounds. |

**Data sources:** [RDKit (descriptors, PAINS)](https://www.rdkit.org/)

Full table: `stages/stage2_adme.csv`

## Stage 3: Compound targets

104 protein targets identified across compounds (target coverage 100.0%) via measured bioactivities.

**Parameters**

| Parameter | Value | Description |
| --- | --- | --- |
| Min Pchembl | 5.0 | Minimum pChEMBL (−log10 molar potency) for a measured compound-target edge. 5 ≈ active at ≤10 µM (standard cutoff); 6 = 1 µM; 7 = 100 nM (stricter). |
| Min Assay Confidence | 7 | Minimum ChEMBL target-confidence score (0-9). 9 = direct single protein; ≥7 high-confidence molecular target; <4 cellular. |

**Data sources:** [ChEMBL](https://www.ebi.ac.uk/chembl/); [PubChem BioAssay](https://pubchem.ncbi.nlm.nih.gov/#query=bioassay); [UniProt](https://www.uniprot.org/)

Full table: `stages/stage3_compound_targets.csv`

## Stage 4: Disease targets

746 proteins associated with Colorectal Cancer (Open Targets, association score >= 0.3): the disease target space.

**Parameters**

| Parameter | Value | Description |
| --- | --- | --- |
| Min Score | 0.3 | Open Targets overall disease-target association score floor. |

**Data sources:** [Open Targets (disease-target associations)](https://platform.opentargets.org/); [UniProt](https://www.uniprot.org/)

Full table: `stages/stage4_disease_targets.csv`

## Stage 5: Target overlap

15 targets shared between the 104 compound targets and 746 disease targets. This is the candidate mechanistic core where the selected plant(s) may act on Colorectal Cancer.

**Data sources:** Set intersection of Stage 3 ∩ Stage 4 (on target_id)

Figure: `stage5_venn.png` · Full table: `stages/stage5_overlap.csv`

## Stage 6: PPI network

The 15 shared targets form a STRING functional-association network: 15 interconnected, 0 isolated. Interconnection suggests a coordinated module rather than independent action.

**Parameters**

| Parameter | Value | Description |
| --- | --- | --- |
| Max Proteins | 2,000 | Self-imposed STRING ceiling; overlaps above this require allow_top_n_cap. |
| Network Type | functional associations (not just physical binding) | STRING network: functional (all association evidence) or physical (binding only). |
| Min Confidence | 0.4 | STRING edge-confidence floor (0-1; tiers 0.15/0.4/0.7/0.9). Default 0.4 = medium. |
| Allow Top N Cap | No | If the overlap exceeds max_proteins, proceed on the top-N by disease-association score. |

**Data sources:** [STRING (protein-protein interactions)](https://string-db.org/); Human only (species 9606); functional or physical

Figure: `stage6_ppi_network.png` · Full table: `stages/stage6_ppi_edges.csv`

## Stage 7: Hub genes

Maximal Clique Centrality (Chin 2014) ranks SMAD3, TP53, JUN as the most topologically central targets, the likely primary mediators. Degree, betweenness, closeness, and eigenvector centrality are reported per target for transparency.

**Parameters**

| Parameter | Value | Description |
| --- | --- | --- |
| Top N | 20 | Number of top-ranked hub genes reported (a descriptive cut, not a significance test). |

**Data sources:** [networkx (centrality analysis)](https://networkx.org/); STRING PPI network (undirected)

*Top hub genes*

| Gene | MCC score |
| --- | --- |
| SMAD3 | 2952 |
| TP53 | 2936 |
| JUN | 2934 |
| EP300 | 2930 |
| EGFR | 2912 |

Figure: `stage7_hub_bar.png` · Full table: `stages/stage7_hubs.csv`

## Stage 8: Functional enrichment

The shared targets are enriched for DNA binding, Pathways in cancer, nucleic acid binding (101 terms, FDR < 0.05), indicating the biological processes through which the selected plant(s) may act on Colorectal Cancer. Strongest: DNA binding (adjusted p = 0.00055, 13 genes). By category: 21 GO molecular function, 8 KEGG, 3 GO cellular component, 69 GO biological process.

**Parameters**

| Parameter | Value | Description |
| --- | --- | --- |
| No IEA | No | Exclude GO terms supported only by electronic (IEA) annotation, keeping curated evidence. |
| Sources | GO biological process, GO molecular function, GO cellular component, KEGG | Annotation vocabularies to query. GO branches + KEGG are the default; Reactome (REAC) and WikiPathways (WP) are additionally selectable. |
| Correction | Benjamini-Hochberg FDR | Multiple-testing correction: BH-FDR (default), g:SCS (GO-aware), or Bonferroni. |
| Min Term Size | 5 | Drop terms smaller than this (avoids tiny, unstable annotations). |
| Significance Threshold | 0.05 | Corrected-p significance cutoff for enriched terms (applies to whichever correction method is selected). |

**Data sources:** [g:Profiler (GO + KEGG enrichment)](https://biit.cs.ut.ee/gprofiler/)

*Top enriched terms*

| Term | Category | Adjusted p | Genes |
| --- | --- | --- | --- |
| DNA binding | GO molecular function | 0.00055 | 13 |
| Pathways in cancer | KEGG | 0.00071 | 11 |
| nucleic acid binding | GO molecular function | 0.0025 | 13 |
| sequence-specific DNA binding | GO molecular function | 0.0038 | 11 |
| Hepatocellular carcinoma | KEGG | 0.0078 | 5 |

Figure: `stage8_enrichment_BP.png` · Full table: `stages/stage8_enrichment.csv`

## How to read these results

- Every compound, target, and pathway links back to the public database it came from; the report records when each source was queried.
- Limitation: we capture *when* and *where* data was fetched, not the exact release version of each external database, so re-running later may differ slightly as sources update.

---
Generated by Herbaflow: http://localhost:5173

