# Compound–Target–Pathway (CTP) network

This document explains the compound–target–pathway network that Herbaflow renders at the top of a
completed analysis and exports as Cytoscape-importable tables. It is written to be quoted directly in a
thesis methods section: it states what the network is, exactly how every node and edge is selected, what
the counts mean, and why the construction follows standard network-pharmacology practice.

## 1. What the network is

Network pharmacology studies a therapy as a *system* of interacting molecules rather than a single
drug acting on a single target. For a medicinal plant, the canonical object of study is the
**compound–target–pathway network**: the plant's small-molecule constituents, the human proteins those
compounds act on, and the biological pathways those proteins participate in. Reading the network from
left to right answers the central mechanistic question of herbal pharmacology: *which constituents act
on which proteins to influence which disease-relevant processes.*

Herbaflow builds this network only over the part of the molecular space that is mechanistically relevant
to the chosen disease, so the figure shows the proposed mechanism of action rather than the full
chemical inventory.

## 2. The three node types

| Node type | What it is | How it is selected |
|-----------|------------|--------------------|
| **Compound** | A plant small molecule | Kept only if, after target prediction, it acts on at least one *shared target* (defined below). Compounds with no shared target are omitted because they carry no edge into the mechanistic core. |
| **Target** | A human protein (gene symbol shown) | The **shared-target set**: the intersection of the compounds' predicted targets and the disease's known targets. This is the mechanistic core of the network. |
| **Pathway** | An enriched biological process or pathway | A functional-enrichment term that is statistically over-represented among the shared targets after multiple-testing correction. |

A target node additionally carries a **hub** flag (rendered as a distinct colour). A hub is a shared
target that ranks among the most topologically central proteins in the protein–protein interaction
network of the shared targets (see §4). Hubs are the proteins most likely to be the mechanistic
bottlenecks of the therapy.

## 3. The two edge types

| Edge | Meaning | Direction | Annotation |
|------|---------|-----------|------------|
| **compound → target** | The compound acts on the protein | compound to target | the prediction method (measured bioactivity or assay outcome) |
| **target → pathway** | The protein is annotated to the enriched term | target to pathway | the term's multiple-testing-adjusted p-value |

A compound–target edge is drawn only when its target is in the shared-target set, so the network never
shows a compound acting on a protein outside the mechanistic core. A target–pathway edge is drawn only
when the protein is one of the genes that drove the term's enrichment (its membership in the term's
intersection set), so pathway links reflect the actual statistical evidence rather than the full
annotation database.

## 4. How each set is determined, step by step

The network is assembled from the outputs of the analysis pipeline. Each upstream step uses a published
method and a fixed, human-only (NCBI taxon 9606) scope.

1. **Plant constituents.** The plant's compounds are taken from a curated phytochemical source
   (KNApSAcK) for a selected plant, or supplied directly by the researcher.
2. **Druglikeness screening.** Compounds are filtered by physicochemical druglikeness descriptors
   (Lipinski and related rules) computed with RDKit, so the network is built from plausibly bioavailable
   molecules.
3. **Compound target prediction.** For each compound, human targets are collected from measured
   bioactivity in ChEMBL (filtered by a potency cutoff, pChEMBL) together with active outcomes in PubChem
   BioAssay. This yields the set of proteins each compound is evidenced to act on.
4. **Disease target collection.** The disease's associated human proteins are taken from Open Targets,
   keeping associations at or above a minimum association score.
5. **Shared targets (the overlap).** The shared-target set is the plain set intersection of the
   compound-predicted targets and the disease targets, computed on a stable protein identifier (the
   UniProt-canonical target). These shared proteins are where the plant's chemistry and the disease
   biology coincide, and they become the **target** nodes of the network.
6. **Protein–protein interaction network.** The shared targets are submitted to STRING to obtain their
   experimentally supported and curated interactions at a confidence cutoff, giving the connectivity
   among the mechanistic core.
7. **Hub ranking.** Hubs are ranked by **Maximal Clique Centrality (MCC)**, the cytoHubba method of Chin
   et al. (2014), computed on the interaction network. The top-ranked proteins are flagged as **hub**
   targets. Four classical centralities (degree, betweenness, closeness, eigenvector) are also reported
   for transparency but are not used for the ranking.
8. **Pathway enrichment.** The shared targets are tested for functional enrichment with g:Profiler
   against a custom background of all compound-predicted targets, across Gene Ontology (biological
   process, molecular function, cellular component), KEGG, Reactome, and WikiPathways. Terms significant
   after multiple-testing correction become the **pathway** nodes.

The compound, target, and pathway nodes of the CTP network are therefore steps 3–8 stitched together:
targets are the step-5 overlap, compounds are the step-3 molecules that bind into that overlap, hubs are
the step-7 ranking, and pathways are the step-8 enriched terms.

## 5. What "how many" means

The network has no fixed node counts. Each count emerges from the data and the thresholds:

- **Number of targets** equals the size of the shared-target overlap, which depends on the compound
  potency cutoff, the disease association-score cutoff, and the underlying biology.
- **Number of compounds** equals how many screened plant molecules bind at least one shared target.
- **Number of pathways** equals how many enrichment terms reach significance after correction.

For example, one completed *Type 2 diabetes* analysis produced a network of **8 compounds, 17 shared
targets (all 17 ranked as hubs), and 28 enriched pathways**, with 29 compound–target edges and 208
target–pathway edges. A different plant, disease, or threshold set produces different counts from the
same construction rules.

## 6. Why this construction is standard

The compound–target–pathway network is the established representation in plant and traditional-medicine
network pharmacology, and every step above maps to a widely used, peer-reviewed method:

- The systems framing and the compound–target–pathway construction follow Hopkins' formulation of
  network pharmacology (Hopkins, 2008).
- Identifying the mechanistic core as the **intersection of drug targets and disease targets** is the
  standard shared-target approach used throughout the herbal network-pharmacology literature.
- Protein interactions come from **STRING** (Szklarczyk et al.), the standard interaction database.
- Hub ranking uses **MCC from cytoHubba** (Chin et al., 2014), a standard topological hub method.
- Enrichment uses **g:Profiler** (Raudvere et al., 2019) over Gene Ontology, KEGG, Reactome, and
  WikiPathways, with multiple-testing correction.
- Disease associations come from **Open Targets** (Ochoa et al.).

The only deliberate scoping choice is that the network is restricted to the shared targets and the
compounds and pathways attached to them, which is what makes it a *mechanism* figure rather than a raw
inventory.

## 7. How to read the figure

- The layout is concentric: shared targets sit toward the centre, compounds in the middle ring, and
  pathways and disease nodes on the outer ring, so the eye moves compound → target → pathway outward.
- Hub targets are drawn in a distinct colour. A pathway linked to many hubs is a process the therapy is
  most strongly predicted to modulate.
- A compound connected to many shared targets is a candidate multi-target constituent; a target
  connected to many compounds is a convergence point of the plant's chemistry.

The interactive view supports hover tooltips, zoom, and fit-to-view, and exports to a transparent-
background PNG for figures. The same node and edge tables are available as Cytoscape-importable CSVs in
the results download for further analysis.

## 8. References

- Hopkins AL (2008). *Network pharmacology: the next paradigm in drug discovery.* Nature Chemical
  Biology 4(11):682–690.
- Chin CH, Chen SH, Wu HH, Ho CW, Ko MT, Lin CY (2014). *cytoHubba: identifying hub objects and
  sub-networks from complex interactome.* BMC Systems Biology 8(Suppl 4):S11.
- Szklarczyk D et al. *STRING* database (current release). Nucleic Acids Research.
- Raudvere U et al. (2019). *g:Profiler: a web server for functional enrichment analysis and conversions
  of gene lists (2019 update).* Nucleic Acids Research 47(W1):W191–W198.
- Ochoa D et al. *Open Targets Platform.* Nucleic Acids Research.
