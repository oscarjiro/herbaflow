"""
PubChem BioAssay integration — secondary target source for NP compounds.

Queries experimental bioactivity data from PubChem BioAssay to find protein
targets for compounds that return 0 results from ChEMBL (e.g., due to lacking
a ChEMBL ID or insufficient activity records).

PubChem aggregates data from BindingDB, ChEMBL, and 300+ primary bioactivity
sources, making it a practical single-call secondary lookup.

Citation:
    Kim S, et al. PubChem 2023 update.
    Nucleic Acids Research 2023, 51(D1):D1373-D1380.
    https://doi.org/10.1093/nar/gkac956
"""

import asyncio
import re
from dataclasses import dataclass

import httpx

from integrations._retry import with_retry, ServiceUnavailableError

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"

# PubChem ToS: ≤ 5 requests/second sustained.
# https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest-tutorial#section=HTTP-Throttling
_SEMAPHORE = asyncio.Semaphore(5)

# UniProt accession format (6-char canonical forms):
#   [A-N,R-Z][0-9][A-Z][A-Z,0-9]{2}[0-9]   (Swiss-Prot / TrEMBL standard)
#   [O,P,Q][0-9][A-Z,0-9]{3}[0-9]
# 10-char secondary accessions also accepted.
_UNIPROT_RE = re.compile(
    r"^([A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]|[OPQ][0-9][A-Z0-9]{3}[0-9])"
    r"([A-Z][A-Z0-9]{3}[0-9])?$"
)


@dataclass
class PubChemTarget:
    uniprot_accession: str
    gene_symbol: str | None
    protein_name: str | None


def _is_uniprot(accession: str) -> bool:
    """Return True if *accession* matches the canonical UniProt format."""
    return bool(_UNIPROT_RE.match(accession.strip().upper()))


async def _get_cid(client: httpx.AsyncClient, inchikey: str) -> int | None:
    """Resolve an InChIKey to a PubChem CID. Returns None on miss or error."""
    url = f"{PUBCHEM_BASE}/compound/inchikey/{inchikey}/cids/JSON"
    async with _SEMAPHORE:
        try:
            async def _fetch_cid() -> httpx.Response:
                r = await client.get(url, timeout=20)
                if r.status_code == 404:
                    return r  # caller checks 404
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_cid, service_name="PubChem BioAssay")
            if resp.status_code == 404:
                return None
        except (httpx.HTTPError, ServiceUnavailableError):
            return None
    cids = resp.json().get("IdentifierList", {}).get("CID", [])
    return cids[0] if cids else None


async def _get_assay_rows(client: httpx.AsyncClient, cid: int) -> list[dict]:
    """
    Fetch the assay summary table for a PubChem CID.

    Returns a list of dicts keyed by column name. Each row represents one
    assay in which this compound was tested. Columns include Activity (or
    ActivityOutcome), TargetAccession, TargetTaxonomyID, TargetSpecies.
    """
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/assaysummary/JSON"
    async with _SEMAPHORE:
        try:
            async def _fetch_assay() -> httpx.Response:
                r = await client.get(url, timeout=30)
                if r.status_code == 404:
                    return r  # caller checks 404
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_assay, service_name="PubChem BioAssay")
            if resp.status_code == 404:
                return []
        except (httpx.HTTPError, ServiceUnavailableError):
            return []
    table = resp.json().get("Table", {})
    columns = table.get("Columns", {}).get("Column", [])
    return [
        dict(zip(columns, row.get("Cell", [])))
        for row in table.get("Row", [])
    ]


async def _resolve_uniprot(
    client: httpx.AsyncClient, accession: str
) -> tuple[str | None, str | None]:
    """
    Fetch (gene_symbol, protein_name) from UniProt REST for a given accession.

    Returns (None, None) on 404 or network error.
    """
    async with _SEMAPHORE:
        try:
            async def _fetch_uniprot() -> httpx.Response:
                r = await client.get(
                    f"{UNIPROT_BASE}/{accession}.json",
                    timeout=15,
                )
                if r.status_code == 404:
                    return r  # caller checks 404
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_uniprot, service_name="UniProt")
            if resp.status_code == 404:
                return None, None
        except (httpx.HTTPError, ServiceUnavailableError):
            return None, None

    data = resp.json()

    gene_symbol: str | None = None
    genes = data.get("genes", [])
    if genes:
        gene_symbol = genes[0].get("geneName", {}).get("value")

    protein_name: str | None = None
    rec_name = data.get("proteinDescription", {}).get("recommendedName", {})
    protein_name = rec_name.get("fullName", {}).get("value")

    return gene_symbol, protein_name


async def get_targets_by_inchikey(
    client: httpx.AsyncClient,
    inchikey: str,
    human_only: bool = True,
) -> list[PubChemTarget]:
    """
    Fetch active protein targets for a compound identified by InChIKey.

    Pipeline:
      1. Resolve InChIKey → PubChem CID.
      2. Fetch assay summary (active assays with protein targets for this CID).
      3. Filter: outcome == "Active", human (taxid 9606), UniProt accession format.
      4. Resolve gene symbol + protein name from UniProt REST.

    Only returns targets where gene_symbol was successfully resolved from UniProt.
    Rate limited to ≤ 5 req/s via module-level semaphore.

    Args:
        client:     Shared httpx.AsyncClient (caller manages lifecycle).
        inchikey:   Standard 27-char InChIKey (e.g., "BSYNRYMUTXBXSQ-UHFFFAOYSA-N").
        human_only: Filter to Homo sapiens (taxid 9606) targets. Default: True.

    Returns:
        List of PubChemTarget with uniprot_accession and gene_symbol set.
        Empty list on any failure or if no active human targets found.
    """
    cid = await _get_cid(client, inchikey)
    if cid is None:
        return []

    rows = await _get_assay_rows(client, cid)
    if not rows:
        return []

    seen: set[str] = set()
    candidates: list[str] = []

    for row in rows:
        # Activity column may appear as "Activity" or "ActivityOutcome" depending
        # on PubChem API version.
        outcome = (row.get("Activity") or row.get("ActivityOutcome") or "").lower()
        if outcome != "active":
            continue

        if human_only:
            tax_id = str(row.get("TargetTaxonomyID") or "")
            species = (row.get("TargetSpecies") or "").lower()
            if tax_id != "9606" and "homo sapiens" not in species:
                continue

        accession = (row.get("TargetAccession") or "").strip()
        if not accession or not _is_uniprot(accession):
            continue  # Skip GenBank GI-only entries (no standard format)

        if accession not in seen:
            seen.add(accession)
            candidates.append(accession)

    if not candidates:
        return []

    # Resolve gene symbols in parallel (each call still bounded by semaphore)
    resolved = await asyncio.gather(
        *[_resolve_uniprot(client, acc) for acc in candidates]
    )

    return [
        PubChemTarget(
            uniprot_accession=acc,
            gene_symbol=gene_symbol,
            protein_name=protein_name,
        )
        for acc, (gene_symbol, protein_name) in zip(candidates, resolved)
        if gene_symbol  # drop entries where UniProt resolution failed
    ]
