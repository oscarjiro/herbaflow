# Herbaflow Backend Design Specification

**Date**: 2026-05-18  
**Status**: Approved  
**Scope**: FastAPI backend + 8-stage network pharmacology analysis pipeline

---

## 1. Problem & Context

Herbaflow is a thesis-grade network pharmacology platform for Indonesian medicinal plants from the KNApSAcK database. The backend must:

1. Expose a REST API over the compound/plant/disease data already in Supabase (11,305 compounds, 10 diseases, 73,469 aliases)
2. Orchestrate an 8-stage analysis pipeline validated against published network pharmacology literature (2020–2025)
3. Support both **automatic mode** (pipeline runs end-to-end) and **guided mode** (user reviews, edits, and approves results at each stage before continuing)
4. Cache intermediate results in Supabase so repeated analyses are fast

The backend directory was deleted and will be scaffolded from scratch.

---

## 2. Architecture

### Layered structure

```
HTTP Request
    ↓
Router          (FastAPI route handlers — validate input, delegate, return response)
    ↓
Service         (business logic — orchestrate pipeline, build responses)
    ↓
Repository      (DB queries — SQLModel selects/inserts, no business logic)
    ↓
Supabase (PostgreSQL)
```

The analysis pipeline is a separate module imported by the service layer:

```
AnalysisService
    ↓
Pipeline Orchestrator (manages stage order and status FSM)
    ↓
Stage Executors       (one per stage, independent, testable)
    ↓
Integration Clients   (ChEMBL, Open Targets, STRING DB, g:Profiler)
```

### Tech stack

| Concern | Choice | Rationale |
|---|---|---|
| Framework | FastAPI | Auto OpenAPI docs, Pydantic validation, native async |
| ORM | SQLModel | Pydantic = ORM models, no duplication, FastAPI native |
| DB migrations | Supabase CLI only | No Alembic — avoid dual-migration conflict |
| Package manager | uv | Fast, modern |
| Async execution | asyncio background tasks | No Redis/Celery — analysis_runs table tracks state |
| Auth | None (single-user) | Add Supabase Auth later if needed |
| Centrality | NetworkX (local) | All 4 metrics, no external API |
| Deployment | Railway | Zero-config, free tier |

---

## 3. Module Map

```
backend/
├── pyproject.toml              # uv deps: fastapi, sqlmodel, asyncpg, httpx, networkx, scipy, pytest
├── app/
│   ├── main.py                 # FastAPI app, lifespan, CORS
│   ├── config.py               # pydantic-settings (DATABASE_URL, optional API keys)
│   ├── database.py             # SQLModel async engine, get_session dep
│   ├── models/                 # SQLModel table=True models (mirror DB schema)
│   │   ├── compound.py
│   │   ├── plant.py
│   │   ├── disease.py
│   │   ├── target.py
│   │   └── analysis.py
│   ├── schemas/                # Pydantic request/response shapes (not table models)
│   │   ├── analysis.py         # CreateAnalysisRequest, AnalysisStatusResponse, AnalysisResultsResponse
│   │   ├── compound.py
│   │   ├── plant.py
│   │   └── disease.py
│   ├── routers/                # Thin route handlers
│   │   ├── plants.py
│   │   ├── compounds.py
│   │   ├── diseases.py
│   │   └── analyses.py
│   ├── services/
│   │   ├── analysis_service.py # Start run, advance stage, approve, poll status
│   │   ├── compound_service.py
│   │   └── disease_service.py
│   └── repositories/
│       ├── compound_repo.py
│       ├── disease_repo.py
│       ├── target_repo.py
│       └── analysis_repo.py
├── analysis/
│   ├── pipeline.py             # Stage registry, orchestrator, status FSM
│   ├── models.py               # StageResult, PipelineInput, PipelineConfig dataclasses
│   └── stages/
│       ├── stage1_selection.py
│       ├── stage2_adme.py
│       ├── stage3_targets.py
│       ├── stage4_disease_targets.py
│       ├── stage5_overlap.py
│       ├── stage6_ppi.py
│       ├── stage7_hub_genes.py
│       └── stage8_enrichment.py
└── integrations/
    ├── chembl.py               # ChEMBL REST API v1 (no key)
    ├── open_targets.py         # Open Targets Platform API (no key; Stage 4 fallback only)
    ├── stringdb.py             # STRING DB API (no key)
    ├── gprofiler.py            # g:Profiler REST API (no key)
    └── stitch.py               # STITCH flat-file lookup (local SQLite; Stage 3 fallback)
```

---

## 4. API Contract

```
GET  /health
GET  /plants
GET  /plants/{id}
GET  /plants/{id}/compounds
GET  /compounds
GET  /compounds/{id}
GET  /diseases
GET  /diseases/{id}

POST /analyses
GET  /analyses
GET  /analyses/{id}
GET  /analyses/{id}/status
POST /analyses/{id}/approve
POST /analyses/{id}/reject
DELETE /analyses/{id}
GET  /analyses/{id}/export/{stage}
```

### POST /analyses request body

```json
{
  "name": "Curcuma longa vs Diabetes",
  "mode": "guided",
  "plant_ids": ["<uuid>"],
  "disease_ids": ["<uuid>"],
  "parameters": {
    "adme": {
      "max_mw": 500, "max_logp": 5, "max_hbd": 5, "max_hba": 10,
      "max_tpsa": 140, "max_rotatable_bonds": 10,
      "apply_veber": true, "apply_pains": false,
      "np_exception_threshold": 0.5
    },
    "target": { "min_pchembl": 5.0, "human_only": true },
    "disease_targets": { "min_score": 0.3 },
    "ppi": { "min_confidence": 0.4 },
    "hub_genes": { "top_n": 20 },
    "enrichment": { "fdr_threshold": 0.05, "sources": ["GO:BP", "GO:MF", "GO:CC", "KEGG"] }
  }
}
```

---

## 5. Analysis State Machine

```
pending
  → stage_N_running → stage_N_awaiting_approval  (guided mode)
                    → stage_(N+1)_running          (auto mode)
  → complete
  → failed
```

Status stored in `analysis_runs.status`. Current stage in `analysis_runs.current_stage` (int 1–8).

---

## 6. Pipeline Stages

### Stage 1 — Compound Selection
Query `plant_compounds JOIN compounds` by input plant_ids. If disease-first entry: load all compounds (disease filter applied at stage 5). No external calls.

### Stage 2 — ADME Screening
Filter in Python against DB-resident Lipinski values. No external calls.

- **Lipinski Ro5**: MW ≤ 500, LogP ≤ 5, HBD ≤ 5, HBA ≤ 10
- **Veber** (optional): TPSA ≤ 140, rotatable_bonds ≤ 10
- **NP exception**: compounds failing Ro5 but with np_likeness_score ≥ 0.5 flagged as "NP exception — include with note" rather than hard-excluded (scientifically justified for plant secondary metabolites)

Output: passed count, failed count, np_exception count, per-compound status.

### Stage 3 — Target Association
For compounds with `chembl_id`: fetch bioactivity from ChEMBL API.  
- Filter: human targets (`target_organism=Homo sapiens`), `pchembl_value >= min_pchembl`  
- Rate limit: `asyncio.Semaphore(10)`

Fallback for compounds with no ChEMBL ID or no hits: STITCH flat-file lookup by `pubchem_cid` (experimental score ≥ 0.4).

Cache results in `targets` + `compound_targets` tables (persistent; re-used on duplicate analyses).

Output: coverage stats (chembl/stitch/none), target-compound matrix.

### Stage 4 — Disease Target Retrieval
Primary: query `disease_targets JOIN targets` in DB (populated by `etl/disease_targets/main.py`).  
Fallback: Open Targets Platform API if disease has no cached targets.

Output: disease-gene association list with scores.

### Stage 5 — Target Overlap
Intersect compound target set ∩ disease target set by normalized gene symbol. Compute:
- Intersection count, Jaccard index, Fisher's exact test p-value (scipy.stats)
- Venn diagram stats for frontend rendering

No external calls.

### Stage 6 — PPI Network Construction
STRING DB API: submit overlapping gene symbols, get edge list (all 7 score channels).  
Build NetworkX graph locally. Store edges in `ppi_edges` table.

Output: Cytoscape.js-compatible JSON (nodes + edges with combined_score).

### Stage 7 — Hub Gene Analysis
All 4 centrality metrics computed with NetworkX:

| Metric | Function | Notes |
|---|---|---|
| Degree | `nx.degree(G)` | Actual edge count (not normalized) |
| Betweenness | `nx.betweenness_centrality(G, normalized=True)` | Identifies bottleneck proteins |
| Closeness | `nx.closeness_centrality(G)` | Proximity to rest of network |
| Eigenvector | `nx.eigenvector_centrality(G, max_iter=1000)` | Influence via neighbors |

Hub threshold: degree ≥ median(degree) + 2·SD(degree).  
Hub-bottleneck flag: is_hub AND betweenness ≥ median(betweenness) + 2·SD(betweenness).  
Output: top 20 by degree. Write to `target_rankings` table.

### Stage 8 — Enrichment Analysis
g:Profiler REST API: submit hub gene symbols, get GO (BP/MF/CC) + KEGG pathway annotations.  
Correction: Benjamini-Hochberg FDR < 0.05.

Output: top 20 significant terms per ontology. Write to `pathways` + `target_pathways` tables.  
Frontend renders: bubble plot (pathway vs −log10(p), sized by intersection).

---

## 7. DB Migrations Required

### migration_1: extend analysis_runs
Add: `current_stage int`, `stage_results jsonb default '{}'`, `mode text default 'auto'`, `completed_at timestamptz`, `error_message text`, `updated_at timestamptz`

### migration_2: verify/add compound columns
Confirm (add if absent): `rotatable_bonds int`, `num_ro5_violations int`, `qed_score float`, `np_likeness_score float`, `lipinski_source text`

### migration_3: pchembl_value on compound_targets
Add: `pchembl_value float` (ChEMBL bioactivity value, nullable)

---

## 8. Pre-requisites Before First Analysis

1. Run `python etl/disease_targets/main.py` to populate `disease_targets` table
2. (Optional) Download STITCH flat file to `backend/data/stitch/` for Stage 3 fallback

---

## 9. Scientific Rationale References

- NeXus v1.2 (2024) — automated multi-layer NP platform: https://pmc.ncbi.nlm.nih.gov/articles/PMC12653797/
- TCM Network Pharmacology Integration Strategy Review (2023): https://pmc.ncbi.nlm.nih.gov/articles/PMC9924699/
- TCMSP Database (2014): https://pubmed.ncbi.nlm.nih.gov/24735618/
- SuperPred 3.0 (NAR 2022): https://academic.oup.com/nar/article/50/W1/W726/6582165
- g:Profiler (NAR 2023): https://academic.oup.com/nar/article/51/W1/W207/7160926
- STRING v12 (NAR 2023): https://academic.oup.com/nar/article/51/D1/D638/6825384
