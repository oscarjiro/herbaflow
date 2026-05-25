# backend/integrations/uniprot.py
"""UniProt REST API client for human protein validation.

Used by T3.3 target add endpoints to validate gene symbols / UniProt accessions
before injecting them into stage_results JSON.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
HUMAN_TAXON_ID = 9606


@dataclass
class UniProtTarget:
    gene_symbol: str
    uniprot_accession: str
    protein_name: str | None


async def validate_human_target(
    gene_symbol: str | None,
    uniprot_id: str | None,
) -> UniProtTarget:
    """Validate a protein against UniProt and confirm it is human (taxon 9606).

    Priority: accession direct lookup (if uniprot_id provided) → gene symbol search.
    Raises ValueError with a user-facing message if:
      - neither input is provided
      - protein not found in UniProt
      - protein is not human
    """
    if not gene_symbol and not uniprot_id:
        raise ValueError("Provide gene_symbol or uniprot_id")

    async with httpx.AsyncClient(timeout=10.0) as client:
        if uniprot_id:
            return await _lookup_by_accession(client, uniprot_id.strip().upper())
        return await _search_by_gene(client, gene_symbol.strip().upper())  # type: ignore[arg-type]


async def _lookup_by_accession(client: httpx.AsyncClient, accession: str) -> UniProtTarget:
    try:
        resp = await client.get(f"{UNIPROT_BASE}/{accession}.json")
    except httpx.HTTPError as exc:
        raise ValueError(f"UniProt request failed: {exc}") from exc
    if resp.status_code == 404:
        raise ValueError(f"UniProt accession '{accession}' not found")
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"UniProt returned error {exc.response.status_code} for '{accession}'") from exc
    try:
        data = resp.json()
    except Exception as exc:
        raise ValueError(f"UniProt returned invalid JSON for '{accession}'") from exc

    taxon = (data.get("organism") or {}).get("taxonId")
    if taxon != HUMAN_TAXON_ID:
        raise ValueError(
            f"UniProt {accession} is not a human protein (taxonId={taxon})"
        )

    gene = _extract_gene(data)
    protein_name = _extract_protein_name(data)
    return UniProtTarget(
        gene_symbol=gene or accession,
        uniprot_accession=accession,
        protein_name=protein_name,
    )


async def _search_by_gene(client: httpx.AsyncClient, gene_symbol: str) -> UniProtTarget:
    try:
        resp = await client.get(
            f"{UNIPROT_BASE}/search",
            params={
                "query": f"gene_exact:{gene_symbol} AND organism_id:{HUMAN_TAXON_ID}",
                "fields": "accession,gene_names,protein_name,organism",
                "size": 1,
                "format": "json",
            },
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"UniProt request failed: {exc}") from exc
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"UniProt search returned error {exc.response.status_code} for '{gene_symbol}'") from exc
    try:
        results = resp.json().get("results", [])
    except Exception as exc:
        raise ValueError(f"UniProt returned invalid JSON for gene '{gene_symbol}'") from exc
    if not results:
        raise ValueError(
            f"Gene symbol '{gene_symbol}' not found as human protein in UniProt"
        )
    entry = results[0]
    accession = entry["primaryAccession"]
    gene = _extract_gene(entry) or gene_symbol
    protein_name = _extract_protein_name(entry)
    return UniProtTarget(
        gene_symbol=gene,
        uniprot_accession=accession,
        protein_name=protein_name,
    )


def _extract_gene(entry: dict) -> str:
    """Pull the primary gene name from a UniProt entry dict."""
    genes = entry.get("genes") or []
    if genes:
        return (genes[0].get("geneName") or {}).get("value", "")
    return ""


def _extract_protein_name(entry: dict) -> str | None:
    """Pull recommended or submitted protein name from a UniProt entry dict."""
    desc = entry.get("proteinDescription") or {}
    rec = desc.get("recommendedName") or {}
    full = rec.get("fullName") or {}
    name = full.get("value")
    if name:
        return name
    # fallback: submittedName
    submitted = desc.get("submittedNames") or []
    if submitted:
        return ((submitted[0].get("fullName") or {}).get("value"))
    return None
