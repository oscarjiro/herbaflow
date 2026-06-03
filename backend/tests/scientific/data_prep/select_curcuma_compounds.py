"""One-time data-prep (NON-CI): select the ADME-screened Curcuma longa compound set
and curcumin, emitting (compound_id, canonical_name, inchi_key, smiles) for STP.

Run:  cd backend && uv run python -m tests.scientific.data_prep.select_curcuma_compounds
Reads DATABASE_URL from the environment (.env). Reuses the platform's own Stage-2
ADME filter so the selection IS the pipeline's screening.
"""
import asyncio
import csv
import os
import sys

import pytest
from sqlalchemy import text

from analysis.models import AdmeParams, CompoundRecord
from analysis.stages.stage2_adme import filter_compounds

CURCUMA_SQL = """
select c.compound_id, c.canonical_name, c.inchi_key, c.smiles,
       c.molecular_weight, c.logp, c.hbond_donors, c.hbond_acceptors,
       c.tpsa, c.rotatable_bonds, c.np_likeness_score, c.is_pains_positive,
       c.num_ro5_violations
from compounds c
join plant_compounds pc on pc.compound_id = c.compound_id
join plants p on p.plant_id = pc.plant_id
where p.canonical_scientific_name ilike '%curcuma longa%'
  and c.smiles is not null and c.smiles <> ''
"""

pytestmark = pytest.mark.scientific


def _row_to_record(row) -> CompoundRecord:
    m = row._mapping
    return CompoundRecord(
        compound_id=str(m["compound_id"]),
        canonical_name=m["canonical_name"] or str(m["compound_id"]),
        smiles=m["smiles"],
        chembl_id=None,
        pubchem_cid=None,
        molecular_weight=m["molecular_weight"],
        logp=m["logp"],
        hbond_donors=m["hbond_donors"],
        hbond_acceptors=m["hbond_acceptors"],
        tpsa=m["tpsa"],
        rotatable_bonds=m["rotatable_bonds"],
        np_likeness_score=m["np_likeness_score"],
        is_pains_positive=bool(m["is_pains_positive"]),
        num_ro5_violations=m["num_ro5_violations"],
        source="plant",
    )


def screen_compounds(records: list[CompoundRecord], params: AdmeParams) -> list[CompoundRecord]:
    """Return compounds that survive the platform's Stage-2 ADME screen (passed + NP exceptions)."""
    result = filter_compounds(records, params)
    return result["passed"] + result["np_exceptions"]


async def _load_records() -> list[CompoundRecord]:
    from app.database import async_session_factory
    async with async_session_factory() as session:
        rows = (await session.execute(text(CURCUMA_SQL))).fetchall()
    return [_row_to_record(r) for r in rows]


def _write_csv(path: str, records: list[CompoundRecord]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["compound_id", "canonical_name", "inchi_key", "smiles"])
        for r in records:
            # inchi_key is not on CompoundRecord; carry it via canonical_name lookup is avoided —
            # emit what the scraper needs: smiles + identity columns it has.
            w.writerow([r.compound_id, r.canonical_name, "", r.smiles])


def main() -> None:
    records = asyncio.run(_load_records())
    screened = screen_compounds(records, AdmeParams())
    out_dir = os.path.join(os.path.dirname(__file__), "_smiles")
    os.makedirs(out_dir, exist_ok=True)
    _write_csv(os.path.join(out_dir, "curcuma_screened_smiles.csv"), screened)

    curcumin = [r for r in records if "curcumin" == (r.canonical_name or "").strip().lower()]
    if not curcumin:
        curcumin = [r for r in records if (r.canonical_name or "").strip().lower() == "curcumin"]
    if len(curcumin) != 1:
        print(f"WARNING: expected exactly 1 curcumin row, found {len(curcumin)}; "
              "verify by InChIKey before scraping P2.", file=sys.stderr)
    _write_csv(os.path.join(out_dir, "curcumin_smiles.csv"), curcumin)
    print(f"screened={len(screened)} curcumin_rows={len(curcumin)} total={len(records)}")


if __name__ == "__main__":
    main()
