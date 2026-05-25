# Audit Session 2 — Phase 1: Target Coverage Expansion

**Date**: 2026-05-25  
**Goal**: Expand ChEMBL-only target identification with secondary sources (STITCH API) and manual STP copy UX to reduce zero-coverage compounds  
**Status**: In progress

---

## Tasks

| Task | Title | Status |
|------|-------|--------|
| T1.1 | Research STITCH API + BindingDB viability | ✅ Complete |
| T1.2 | Backend PubChem BioAssay integration in Stage 3 (STITCH rejected) | ✅ Complete |
| T1.3 | Per-compound source tracking in Stage 3 output | ✅ Complete |
| T1.4 | Frontend STP copy UX — coverage panel, export, import | Pending |
| T1.5 | Scientific documentation + citations | Pending |

---

## T1.1 — Research STITCH API + BindingDB

*See: `.superpowers/audit-session-2/phase-1-t1.md` for full findings*

**Outcome**: STITCH rejected (TLS cert invalid, last update 2016, effectively unmaintained). BindingDB direct API rejected (endpoints 404, API restructured). **PubChem BioAssay selected** as secondary source.

Key facts:
- PubChem PUG REST: `GET /compound/inchikey/{ik}/assaysummary/JSON` — InChIKey native, NCBI-maintained, 5 req/s rate limit
- Aggregates BindingDB + STITCH + 300+ sources — querying PubChem subsumes both rejected candidates
- T1.2 plan amended: `backend/integrations/stitch.py` → `backend/integrations/pubchem_bioassay.py`
- Citation: Kim et al. *Nucleic Acids Research* 2023, 51(D1):D1373–D1380

**Status**: ✅ Complete. See `.superpowers/audit-session-2/phase-1-t1.md` for full findings and implementation pseudocode.

---

## T1.2 — Backend PubChem BioAssay Integration

Commit: `c8bc126` — `feat(backend/stage3): add PubChem BioAssay as secondary target source`

- Created `backend/integrations/pubchem_bioassay.py`: `get_targets_by_inchikey()` — InChIKey → PubChem CID → assay summary → filter Active/human/UniProt → resolve gene symbol + protein name. Rate limited: `asyncio.Semaphore(5)`.
- Extended `backend/analysis/stages/stage3_targets.py`: after ChEMBL, compounds with 0 targets + valid `inchi_key` queried in parallel via PubChem. Results merged into unified `target_compound_map`. CT rows tagged `prediction_method="pubchem_bioassay"`, `pchembl_value=None`.
- 2 new unit tests in `backend/tests/unit/test_stage3.py`.

**Status**: ✅ Complete.

---

## T1.3 — Source Tracking

Files changed:
- `backend/analysis/stages/stage3_targets.py`: each target in `targets` list tagged with `source: "chembl" | "pubchem_bioassay"`; output includes `compound_sources: {compound_id: [source, ...]}` mapping
- `frontend/src/types/api.ts`: `TargetResult.source` added; `Stage3Result.compound_sources` added
- `frontend/src/components/stages/Stage3Panel.tsx`: Source column added to targets DataTable with colored badges (sage = ChEMBL, terracotta = PubChem BioAssay); attribution text updated to mention both sources with Kim et al. 2023 citation

Verification: 63 backend tests pass; frontend lint errors pre-existing (unrelated files).

**Status**: ✅ Complete.
