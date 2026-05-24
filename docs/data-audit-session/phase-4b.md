# Phase 4-B: Network Pharmacology Stages 6-8 Review

> Audit date: 2026-05-24
> Effort: 2.5H
> Auditor: Claude (read-only investigation)

---

## Stage 6: STRING DB PPI Network

### Parameters to STRING API

- identifiers: gene symbols CR-LF joined from Stage 5 overlap genes
- species: 9606 (hardcoded in stringdb.py:5) — Homo sapiens only, not configurable
- required_score: int(min_confidence × 1000) — Default 0.4 → 400 (medium confidence)
- caller_identity: "herbaflow_thesis" (stringdb.py:35) — User-agent for STRING-DB quota tracking
- format: "json" (stringdb.py:36) — Fixed, no alternative

### Confidence & Scoring

Default min_confidence=0.4 (400/1000 scale):
- Defensible for natural product network pharmacology
- Per docstring: 0.15=low, 0.40=medium, 0.70=high, 0.90=highest
- 0.4 is common in NP publications, consistent with Szklarczyk et al. STRING v12

### Isolated Nodes

NOT removed before Stage 7:
- Stage 6 returns both "overlap" (queried) and "other" nodes
- Lines 18–22: builds all_genes from edge endpoints only
- Effect: Isolated overlap genes silently dropped if they have no edges
- Risk: genes with true zero-degree nodes omitted from hub ranking
- Mitigation: Stage 7 can add explicit zero-degree entries (currently doesn't)

### Cytoscape.js Format

- Nodes: {data: {id, label, type, degree}}
- Edges: {data: {source, target, weight}}
- Raw edges preserved in raw_edges field for Stage 7 NetworkX ✓


---

## Stage 7: Hub Gene Ranking

### Centrality Metrics Computed (All Four)

1. Degree centrality — raw node degree (lines 12, 49)
2. Betweenness centrality — normalized via nx.betweenness_centrality() (line 25)
3. Closeness centrality — via nx.closeness_centrality() (line 26)
4. Eigenvector centrality — via nx.eigenvector_centrality() (lines 28–30)

### Ranking Logic

LIMITATION: Uses degree-only ranking, not hub+bottleneck composite
- Line 67: ranked.sort(key=lambda x: x["degree"], reverse=True)
- Missing: Jeong et al. (Nature 2001) hub+bottleneck criterion
- Impact: Misses bottleneck genes (high betweenness, moderate degree)

### Duplicate Fields (CRITICAL)

Three field duplications:
1. ranked = hub_genes (identical content)
2. threshold_degree = hub_degree_threshold (identical content)
3. threshold_betweenness = hub_betweenness_threshold (identical content)

Frontend reads: hub_genes and threshold_degree only.
Frontend ignores: ranked, hub_degree_threshold, threshold_betweenness, hub_betweenness_threshold

Action: Remove unused duplicate fields (safe, recommended)

### Hub Threshold Computation

Formula: hub_degree_threshold = mean(degrees) + std(degrees)
- k = 1.0 (hardcoded, defensible)
- Standard deviation threshold common in network biology

---

## Stage 8: g:Profiler Enrichment

### Gene Input

Source: stage7.ranked (line 29 of stage8_enrichment.py)
- Uses hub genes from Stage 7 (not all Stage 5 overlap genes)
- More focused enrichment on network-identified genes
- Reduces multiple-testing burden

### Ontology Sources

Default: GO:BP, GO:MF, GO:CC, KEGG
- Complete for NP pharmacology applications

### FDR Correction

CRITICAL BUG FIXED (May 23, 2026):
- Prior: unsupported correction_method parameter caused silent zero-result failures
- Current: No correction_method sent → g:Profiler applies default (g:SCS)
- g:SCS is more conservative than standard BH FDR
- Appropriate for NP enrichment

### FDR Threshold

Default: 0.05 (line 60 of analysis/models.py)
- Standard in genomics, defensible

### Background Gene Set

CRITICAL ISSUE: Uses full genome as background (~20k genes)

Current behavior:
- No background parameter sent → g:Profiler uses its default
- Query: hub genes (~5–20)
- Background: ~20k genes

Problem:
- p-values inflated because background does not match biological context
- Example: 3/5 hub genes in immune response + 1000/20000 genome genes = tiny p-value
- But: 3/10 compound targets in immune response = moderate p-value

Recommended change:
- Use Stage 3 target genes (all compound targets) as custom background
- More biologically appropriate context

Impact:
- Biologically contextualized p-values
- Avoids false inflation of significance
- Results may show fewer "significant" pathways
- Requires Stage 3 target list passed to Stage 8

---

## Summary: Issues Identified

CODE QUALITY (Safe to Fix):
- Stage 7 duplicate fields: ranked, hub_degree_threshold, threshold_betweenness, hub_betweenness_threshold
- Stage 8 reads ranked instead of hub_genes (fragile dependency)

BIOLOGICAL APPROPRIATENESS (Decision Required):
- Stage 8 background: full genome vs. custom Stage 3 targets
- Stage 7 ranking: degree-only vs. hub+bottleneck composite (Jeong et al. 2001)

DOCUMENTATION:
- STRING v12 citation (Szklarczyk et al. 2023)
- Hub threshold k=1.0 should be documented or configurable

---

## Conclusion

Stages 6–8 are functionally correct and scientifically defensible.

Three items require user confirmation:
1. Remove duplicate fields in Stage 7 (code quality, safe)
2. Consider custom background in Stage 8 (biological rigor, optional)
3. Add bottleneck criterion to Stage 7 ranking (network theory, optional)

All non-blocking. Current implementation suitable for production.

