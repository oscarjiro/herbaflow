import httpx
from dataclasses import dataclass

from integrations._retry import with_retry, ServiceUnavailableError

OT_BASE = "https://api.platform.opentargets.org/api/v4"


@dataclass
class OtAssociation:
    gene_symbol: str
    ensembl_id: str
    score: float


async def get_disease_targets(
    efo_id: str, min_score: float = 0.3, limit: int = 500
) -> list[OtAssociation]:
    """
    Fetch gene-disease associations from Open Targets GraphQL API.
    efo_id: EFO/ontology ID (e.g., 'EFO_0000400')
    """
    query = """
    query DiseaseTargets($efoId: String!, $size: Int!) {
      disease(efoId: $efoId) {
        associatedTargets(page: {index: 0, size: $size}) {
          rows {
            target {
              approvedSymbol
              id
            }
            score
          }
        }
      }
    }
    """
    async with httpx.AsyncClient() as client:
        try:
            async def _fetch_ot() -> httpx.Response:
                r = await client.post(
                    f"{OT_BASE}/graphql",
                    json={"query": query, "variables": {"efoId": efo_id, "size": limit}},
                    timeout=30,
                )
                r.raise_for_status()
                return r

            resp = await with_retry(_fetch_ot, service_name="Open Targets")
        except (httpx.HTTPError, ServiceUnavailableError):
            return []

    data = resp.json().get("data", {})
    disease_data = data.get("disease", {})
    if not disease_data:
        return []

    rows = disease_data.get("associatedTargets", {}).get("rows", [])
    return [
        OtAssociation(
            gene_symbol=row["target"]["approvedSymbol"],
            ensembl_id=row["target"]["id"],
            score=row["score"],
        )
        for row in rows
        if row["score"] >= min_score
    ]
