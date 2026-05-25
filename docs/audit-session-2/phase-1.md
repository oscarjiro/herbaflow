# Audit Session 2 — Phase 1: Target Coverage Expansion

**Date**: 2026-05-25  
**Goal**: Expand ChEMBL-only target identification with secondary sources (PubChem BioAssay) and manual STP copy UX to reduce zero-coverage compounds.

---

## Tasks

| Task | Title | Status |
|------|-------|--------|
| T1.1 | Research STITCH API + BindingDB viability | ✅ Complete |
| T1.2 | Backend PubChem BioAssay integration in Stage 3 | ✅ Complete |
| T1.3 | Per-compound source tracking in Stage 3 output | ✅ Complete |
| T1.4 | Frontend STP copy UX — coverage panel, export, import | ✅ Complete |
| T1.5 | Scientific documentation + citations | ✅ Complete |

---

## T1.1 — Research STITCH API + BindingDB

*Detail: `.superpowers/audit-session-2/phase-1-t1.md`*

**Outcome**: STITCH rejected (TLS cert invalid, last update 2016, effectively unmaintained). BindingDB direct API rejected (endpoints 404, API restructured). **PubChem BioAssay selected** as secondary source.

Key facts:
- PubChem PUG REST: `GET /compound/inchikey/{ik}/assaysummary/JSON` — InChIKey native, NCBI-maintained, 5 req/s rate limit
- Aggregates BindingDB + STITCH + 300+ sources — querying PubChem subsumes both rejected candidates
- Citation: Kim et al. *Nucleic Acids Research* 2023, 51(D1):D1373–D1380

---

## T1.2 — Backend PubChem BioAssay Integration

**Commit**: `c8bc126 feat(backend/stage3): add PubChem BioAssay as secondary target source`

- Created `backend/integrations/pubchem_bioassay.py`: `get_targets_by_inchikey()` — InChIKey → PubChem CID → assay summary → filter Active/human/UniProt → resolve gene symbol + protein name. Rate limited: `asyncio.Semaphore(5)`.
- Extended `backend/analysis/stages/stage3_targets.py`: after ChEMBL, compounds with 0 targets + valid `inchi_key` queried in parallel via PubChem. Results merged into unified `target_compound_map`. CT rows tagged `prediction_method="pubchem_bioassay"`, `pchembl_value=None`.
- 2 new unit tests in `backend/tests/unit/test_stage3.py`.

---

## T1.3 — Source Tracking

Files changed:
- `backend/analysis/stages/stage3_targets.py`: each target tagged with `source: "chembl" | "pubchem_bioassay"`; output includes `compound_sources: {compound_id: [source, ...]}` mapping
- `frontend/src/types/api.ts`: `TargetResult.source` added; `Stage3Result.compound_sources` added
- `frontend/src/components/stages/Stage3Panel.tsx`: Source column with colored badges (sage = ChEMBL, terracotta = PubChem BioAssay)

---

## T1.4 — Frontend STP Coverage UX

**Commits**: `9573a73`–`a3c2813`

- Coverage section added to `Stage3Panel.tsx`: coverage stat card, covered/uncovered counts, export SMILES CSV button, import STP results toggle
- STP import panel: compound selector (uncovered flagged "⚠ 0 targets"), drag-drop/paste CSV input, probability slider (default 0.1), CSV preview table, `parseSTPCsv` / `generateSTPExportCsv` utilities in `frontend/src/lib/stp.ts`
- Backend: `POST /analyses/{id}/import-targets` endpoint + `_merge_stp_targets` helper in `backend/app/routers/analyses.py`; schemas at `backend/app/schemas/import_targets.py`; `prediction_method="stp_import"`, `evidence_type="computational"` on DB rows
- 10 unit tests for `stp.ts`; 102 tests total passing (68 backend + 34 frontend)

---

## T1.5 — Scientific Documentation + Citations

### Source Hierarchy

| Priority | Source | Method | Evidence type | DB column |
|----------|--------|--------|--------------|-----------|
| 1 | ChEMBL | Bioactivity (pChEMBL ≥ 5.0, confidence ≥ 7) | Experimental | `prediction_method="chembl"` |
| 2 | PubChem BioAssay | Assay summary (Active, human, UniProt) | Experimental | `prediction_method="pubchem_bioassay"` |
| 3 | SwissTargetPrediction | Similarity + ML (user-set probability threshold) | Computational | `prediction_method="stp_import"` |

### Citations

- Kim S et al. (2023). *PubChem 2023 update.* Nucleic Acids Res 51(D1):D1373–D1380. *(PubChem BioAssay)*
- Daina A, Michielin O, Zoete V (2019). *SwissTargetPrediction: updated data and new features.* Nucleic Acids Res 47(W1):W357–W364. *(STP import)*
