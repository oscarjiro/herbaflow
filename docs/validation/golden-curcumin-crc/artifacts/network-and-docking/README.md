# Network & docking handoff

This folder contains the compound-target-pathway (C-T-P) network in a format ready for
Cytoscape, a static PNG rendering of that network, and a docking-preparation table that pairs
each hub protein with the compounds that bind it.

## Files

- `ctp-nodes.csv` / `ctp-edges.csv`: the C-T-P network (Cytoscape node and edge tables).
- `ctp-network.png`: a static rendering of the network (may be absent for very large networks).
- `ppi-nodes.csv` / `ppi-edges.csv`: the protein-protein interaction (PPI) sub-network
  (Stage 6); useful if you want to visualise only the target layer.
- `docking.csv`: one row per hub protein x binding compound pair, ready to feed into a
  structure-based docking tool (e.g. AutoDock Vina).

## Import the network into Cytoscape (desktop)

1. Open **File → Import Network from File** and choose `ctp-edges.csv`.
   Map `source` and `target` to the source/target node columns; `interaction` is the edge type.
2. Open **File → Import Table from File** and choose `ctp-nodes.csv`, matched on the `id` column.
   This attaches `label`, `type`, `is_hub`, etc. as node attributes you can style by.

The edge endpoint strings equal the node `id` strings, so the join is exact.

## Columns

### ctp-nodes.csv

| Column | Meaning |
|---|---|
| `id` | Node id: compound InChIKey, target gene symbol, or pathway term id (e.g. `GO:0045944`). |
| `label` | Human-readable display name (compound name, gene symbol, or term name). |
| `type` | Node type: `compound`, `target`, or `pathway`. |
| `inchikey` | InChIKey for compound nodes (27-char structural hash); blank otherwise. |
| `smiles` | **SMILES** of the compound (2-D); ligand input for docking. Blank otherwise. |
| `uniprot_accession` | UniProt accession (e.g. `P37231`) for target nodes; blank otherwise. |
| `is_hub` | `true` if this target was ranked as a hub gene (Stage 7); blank for non-target nodes. |
| `source` | Pathway DB source for pathway nodes (e.g. `KEGG`, `GO:BP`, `REAC`); blank otherwise. |

### ctp-edges.csv

| Column | Meaning |
|---|---|
| `source` | Node id of the edge's origin (compound InChIKey or target gene symbol). |
| `target` | Node id of the edge's destination (target gene symbol or pathway term id). |
| `interaction` | `compound-target` (Stage 3 bioactivity) or `target-pathway` (Stage 8). |
| `prediction_method` | Compound-target evidence: `chembl_bioactivity` or `pubchem_bioassay`. |
| `p_value` | Target-pathway edges: BH-corrected enrichment p-value (full precision); else blank. |

### docking.csv

| Column | Meaning |
|---|---|
| `hub_gene_symbol` | Gene symbol of the hub target (Stage 7 top-ranked proteins). |
| `hub_uniprot_accession` | UniProt accession of the hub protein. |
| `alphafold_id` | **AlphaFold** model id (= `hub_uniprot_accession`); predicted 3-D structure. |
| `compound_name` | Common name of the binding compound. |
| `compound_inchikey` | InChIKey of the binding compound (stable structural identifier). |
| `compound_smiles` | **SMILES** of the binding compound (the ligand input for docking). |
| `prediction_method` | Evidence source for the compound-target interaction. |
| `source_url` | AlphaFold model page for the hub protein (links to the predicted structure). |

## How to use docking.csv

Each row in `docking.csv` describes one candidate docking experiment:

- **Protein (receptor)**: download the **AlphaFold** predicted structure for the UniProt accession
  in `hub_uniprot_accession` (the `source_url` column links directly to the model page). Save the
  structure as PDB or mmCIF.
- **Ligand**: the compound's **SMILES** string in `compound_smiles` encodes its 2-D chemical
  structure. Convert it to a 3-D conformer using a tool such as RDKit or OpenBabel, then prepare
  the ligand file in the format your docking tool expects (e.g. PDBQT for AutoDock Vina).
- **Docking**: run your chosen docking tool (e.g. AutoDock Vina) with the AlphaFold receptor
  structure and the prepared ligand. The predicted binding affinity (kcal/mol) is your primary
  output.

The table already filters to hub proteins only. These are the mechanistically central targets
identified by the network analysis, so they are the highest-priority candidates for docking.
