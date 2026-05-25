# Audit Session 2 — Phase 1: Target Coverage Expansion

**Date**: 2026-05-25  
**Goal**: Expand ChEMBL-only target identification with secondary sources (STITCH API) and manual STP copy UX to reduce zero-coverage compounds  
**Status**: In progress

---

## Tasks

| Task | Title | Status |
|------|-------|--------|
| T1.1 | Research STITCH API + BindingDB viability | ✅ Complete |
| T1.2 | Backend PubChem BioAssay integration in Stage 3 (STITCH rejected) | Pending |
| T1.3 | Per-compound source tracking in Stage 3 output | Pending |
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
