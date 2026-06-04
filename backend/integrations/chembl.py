import asyncio
import logging
from dataclasses import dataclass

import httpx

from integrations._retry import ServiceUnavailableError, with_retry

logger = logging.getLogger(__name__)

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
SEMAPHORE = asyncio.Semaphore(10)


@dataclass
class ChemblTarget:
    chembl_id: str
    gene_symbol: str | None
    uniprot_accession: str | None
    organism: str | None
    pchembl_value: float | None


@dataclass
class ChemblBioactivity:
    molecule_chembl_id: str
    target_chembl_id: str
    pchembl_value: float | None
    target_organism: str | None
    assay_type: str | None


async def get_bioactivities(
    client: httpx.AsyncClient,
    molecule_chembl_id: str,
    min_pchembl: float = 5.0,
    human_only: bool = True,
    min_assay_confidence: int = 7,
) -> list[ChemblBioactivity]:
    params = {
        "molecule_chembl_id": molecule_chembl_id,
        "limit": 1000,
        "offset": 0,
        "format": "json",
    }
    if human_only:
        params["target_organism"] = "Homo sapiens"
    if min_assay_confidence > 0:
        params["assay_confidence_score__gte"] = min_assay_confidence

    async with SEMAPHORE:
        try:
            async def _fetch_bioactivities() -> httpx.Response:
                r = await client.get(f"{CHEMBL_BASE}/activity.json", params=params, timeout=30)
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_bioactivities, service_name="ChEMBL")
        except ServiceUnavailableError:
            logger.error("ChEMBL unavailable after retries (bioactivities for %s)", molecule_chembl_id)
            raise
        except httpx.HTTPError as exc:
            logger.error("ChEMBL HTTP error fetching bioactivities for %s: %s", molecule_chembl_id, exc)
            return []

    data = resp.json()
    activities = []
    for row in data.get("activities", []):
        pchembl = row.get("pchembl_value")
        if pchembl is not None:
            try:
                pchembl = float(pchembl)
            except (TypeError, ValueError):
                pchembl = None

        if min_pchembl and (pchembl is None or pchembl < min_pchembl):
            continue

        target_chembl_id = row.get("target_chembl_id")
        if not target_chembl_id:
            continue

        activities.append(ChemblBioactivity(
            molecule_chembl_id=molecule_chembl_id,
            target_chembl_id=target_chembl_id,
            pchembl_value=pchembl,
            target_organism=row.get("target_organism"),
            assay_type=row.get("assay_type"),
        ))

    return activities


async def resolve_target(
    client: httpx.AsyncClient, target_chembl_id: str
) -> ChemblTarget | None:
    async with SEMAPHORE:
        try:
            async def _fetch_target() -> httpx.Response:
                r = await client.get(
                    f"{CHEMBL_BASE}/target/{target_chembl_id}.json",
                    timeout=20,
                )
                if r.status_code == 404:
                    return r  # caller checks 404 — don't raise_for_status
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_target, service_name="ChEMBL")
            if resp.status_code == 404:
                return None
        except ServiceUnavailableError:
            logger.error("ChEMBL unavailable after retries (target %s)", target_chembl_id)
            raise
        except httpx.HTTPError as exc:
            logger.error("ChEMBL HTTP error resolving target %s: %s", target_chembl_id, exc)
            return None

    data = resp.json()
    gene_symbol = None
    uniprot = None

    for component in data.get("target_components", []):
        for synonym in component.get("target_component_synonyms", []):
            if synonym.get("syn_type") == "GENE_SYMBOL":
                gene_symbol = synonym.get("component_synonym")
            if synonym.get("syn_type") == "UNIPROT":
                uniprot = synonym.get("component_synonym")

    return ChemblTarget(
        chembl_id=target_chembl_id,
        gene_symbol=gene_symbol,
        uniprot_accession=uniprot,
        organism=data.get("organism"),
        pchembl_value=None,
    )


async def get_targets_for_compounds(
    chembl_ids: list[str],
    min_pchembl: float = 5.0,
    human_only: bool = True,
    min_assay_confidence: int = 7,
) -> dict[str, list[ChemblTarget]]:
    target_cache: dict[str, ChemblTarget] = {}
    compound_targets: dict[str, list[ChemblTarget]] = {cid: [] for cid in chembl_ids}

    async with httpx.AsyncClient() as client:
        tasks = [get_bioactivities(client, cid, min_pchembl, human_only, min_assay_confidence) for cid in chembl_ids]
        all_bioactivities = await asyncio.gather(*tasks)

        unique_target_ids = set()
        for activities in all_bioactivities:
            for act in activities:
                unique_target_ids.add(act.target_chembl_id)

        resolve_tasks = [resolve_target(client, tid) for tid in unique_target_ids]
        resolved = await asyncio.gather(*resolve_tasks)
        for target in resolved:
            if target and target.gene_symbol:
                target_cache[target.chembl_id] = target

        for cid, activities in zip(chembl_ids, all_bioactivities):
            seen_targets = set()
            for act in activities:
                target = target_cache.get(act.target_chembl_id)
                if target and target.gene_symbol not in seen_targets:
                    target_with_pchembl = ChemblTarget(
                        chembl_id=target.chembl_id,
                        gene_symbol=target.gene_symbol,
                        uniprot_accession=target.uniprot_accession,
                        organism=target.organism,
                        pchembl_value=act.pchembl_value,
                    )
                    compound_targets[cid].append(target_with_pchembl)
                    seen_targets.add(target.gene_symbol)

    return compound_targets
