# Phase 6: Compliance + Docs Sync

## T6.1 — Audit-Session-2 Compliance Check

### Backend Tests
Backend tests: 180 passing, 0 failing.

### Frontend Build
TypeScript errors: 0 (built successfully in 27.42s, 2579 modules transformed).

### Feature Compliance
| Feature | Status | Location |
|---|---|---|
| PubChem BioAssay | ✅ | `backend/integrations/pubchem_bioassay.py`; called in `backend/analysis/stages/stage3_targets.py` (imports `get_targets_by_inchikey`, used as fallback source) |
| Manual compounds mode | ✅ | `backend/analysis/pipeline.py` line 117 — `"manual_compounds": 3` skip-routing entry; handled by `_input_mode` param in `backend/app/schemas/analysis.py` |
| Manual targets mode | ✅ | `backend/analysis/pipeline.py` line 118 — `"manual_targets": 4` skip-routing entry; schema in `backend/app/schemas/analysis.py` |
| Multi-disease support | ✅ | `backend/analysis/stages/stage4_disease_targets.py` line 41 — `disease_ids = params.get("_disease_ids", [])` iterates over list; `backend/app/schemas/analysis.py` line 94 — `disease_ids: list[str]` |
| Stage skip routing | ✅ | `backend/analysis/pipeline.py` lines 137–155 — `_input_mode` read from params, skipped stages written as `{"status": "skipped", "input_mode": ...}` |
| Add/remove user targets | ✅ | `frontend/src/hooks/useAddUserTarget.ts`; `frontend/src/hooks/useRemoveUserTarget.ts` |
| Zod frontend schemas | ✅ | `frontend/src/lib/schemas.ts` |
| Pydantic backend constraints | ✅ | `backend/app/schemas/analysis.py` — `Field(...)` constraints on `name`, `plant_ids`, `disease_ids`, `parameters`, `compounds`, `targets` |
| StageSkeletonLoader | ✅ | `frontend/src/components/shared/StageSkeletonLoader.tsx` |
| ExportButton all stages | ✅ | `backend/app/routers/analyses.py` line 234 — `GET /{analysis_id}/export/{stage}` dynamic route; CSV serialization implemented for all stages 1–8 |

### Notes
- The audit task specification referenced `backend/analysis/integrations/pubchem_bioassay.py` — the actual path is `backend/integrations/pubchem_bioassay.py` (one level up, alongside `chembl.py`, `open_targets.py`, etc.). The integration is fully functional and called in stage3.
- No dedicated `export.py` router exists; export is co-located in `backend/app/routers/analyses.py`.

T6.1 complete.

## T6.3 — Final Verification

| Check | Result |
|---|---|
| Backend tests | 180 passing, 0 failing |
| Frontend tests | 60 passing, 0 failing |
| TypeScript | 0 errors |

Audit-session-2.5 complete.
