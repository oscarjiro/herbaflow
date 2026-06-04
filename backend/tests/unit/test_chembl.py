"""Unit tests for integrations/chembl.py.

Tests get_bioactivities, resolve_target, and get_targets_for_compounds
using mock httpx clients — no real HTTP calls.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from integrations._retry import ServiceUnavailableError
from integrations.chembl import (
    ChemblBioactivity,
    ChemblTarget,
    get_bioactivities,
    get_targets_for_compounds,
    resolve_target,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resp(data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_activity_row(
    target_chembl_id: str = "CHEMBL301",
    pchembl_value: str | None = "7.5",
    target_organism: str = "Homo sapiens",
    assay_type: str = "B",
) -> dict:
    return {
        "target_chembl_id": target_chembl_id,
        "pchembl_value": pchembl_value,
        "target_organism": target_organism,
        "assay_type": assay_type,
    }


def _make_target_data(
    chembl_id: str = "CHEMBL301",
    gene_symbol: str = "AKT1",
    uniprot: str = "P31749",
    organism: str = "Homo sapiens",
) -> dict:
    return {
        "target_chembl_id": chembl_id,
        "organism": organism,
        "target_components": [
            {
                "target_component_synonyms": [
                    {"syn_type": "GENE_SYMBOL", "component_synonym": gene_symbol},
                    {"syn_type": "UNIPROT", "component_synonym": uniprot},
                ]
            }
        ],
    }


# ---------------------------------------------------------------------------
# get_bioactivities — returns ChemblBioactivity list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_bioactivities_returns_parsed_activities():
    """get_bioactivities returns ChemblBioactivity objects from JSON response."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = _make_resp({
        "activities": [_make_activity_row("CHEMBL301", "7.5")]
    })

    async def passthrough(fn, **kwargs):
        return await fn()

    with patch("integrations.chembl.with_retry", side_effect=passthrough):
        mock_client.get = AsyncMock(return_value=resp)
        result = await get_bioactivities(mock_client, "CHEMBL12345")

    assert len(result) == 1
    assert isinstance(result[0], ChemblBioactivity)
    assert result[0].target_chembl_id == "CHEMBL301"
    assert result[0].pchembl_value == pytest.approx(7.5)
    assert result[0].target_organism == "Homo sapiens"


@pytest.mark.asyncio
async def test_get_bioactivities_filters_by_pchembl_threshold():
    """Activities with pChEMBL < min_pchembl (default 5.0) are excluded."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = _make_resp({
        "activities": [
            _make_activity_row("CHEMBL301", "7.5"),  # above threshold → included
            _make_activity_row("CHEMBL302", "4.0"),  # below threshold → excluded
            _make_activity_row("CHEMBL303", "5.0"),  # equal → included
        ]
    })

    async def passthrough(fn, **kwargs):
        return await fn()

    with patch("integrations.chembl.with_retry", side_effect=passthrough):
        mock_client.get = AsyncMock(return_value=resp)
        result = await get_bioactivities(mock_client, "CHEMBL_MOL_1", min_pchembl=5.0)

    target_ids = {r.target_chembl_id for r in result}
    assert "CHEMBL301" in target_ids
    assert "CHEMBL303" in target_ids
    assert "CHEMBL302" not in target_ids


@pytest.mark.asyncio
async def test_get_bioactivities_excludes_none_pchembl():
    """Activities with pchembl_value=None are excluded when min_pchembl > 0."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = _make_resp({
        "activities": [
            _make_activity_row("CHEMBL301", None),  # no pChEMBL → excluded
            _make_activity_row("CHEMBL302", "6.0"),  # has pChEMBL → included
        ]
    })

    async def passthrough(fn, **kwargs):
        return await fn()

    with patch("integrations.chembl.with_retry", side_effect=passthrough):
        mock_client.get = AsyncMock(return_value=resp)
        result = await get_bioactivities(mock_client, "CHEMBL_MOL_X", min_pchembl=5.0)

    assert len(result) == 1
    assert result[0].target_chembl_id == "CHEMBL302"


@pytest.mark.asyncio
async def test_get_bioactivities_human_only_filter_via_params():
    """When human_only=True, target_organism param is sent in request."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = _make_resp({"activities": []})

    async def passthrough(fn, **kwargs):
        return await fn()

    with patch("integrations.chembl.with_retry", side_effect=passthrough):
        mock_client.get = AsyncMock(return_value=resp)
        await get_bioactivities(mock_client, "CHEMBL_MOL_Y", human_only=True)

    call_kwargs = mock_client.get.call_args
    sent_params = call_kwargs[1].get("params", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {})
    assert sent_params.get("target_organism") == "Homo sapiens"


@pytest.mark.asyncio
async def test_get_bioactivities_raises_on_service_unavailable():
    """ServiceUnavailableError propagates out instead of collapsing to empty list."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("integrations.chembl.with_retry",
               side_effect=ServiceUnavailableError("ChEMBL", last_status=503)):
        with pytest.raises(ServiceUnavailableError):
            await get_bioactivities(mock_client, "CHEMBL_MOL_Z")


# ---------------------------------------------------------------------------
# resolve_target — returns ChemblTarget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_target_returns_chembl_target():
    """resolve_target parses gene_symbol and uniprot from target_component_synonyms."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = _make_resp(_make_target_data("CHEMBL301", "AKT1", "P31749"))

    async def passthrough(fn, **kwargs):
        return await fn()

    with patch("integrations.chembl.with_retry", side_effect=passthrough):
        mock_client.get = AsyncMock(return_value=resp)
        result = await resolve_target(mock_client, "CHEMBL301")

    assert result is not None
    assert isinstance(result, ChemblTarget)
    assert result.gene_symbol == "AKT1"
    assert result.uniprot_accession == "P31749"
    assert result.chembl_id == "CHEMBL301"
    assert result.organism == "Homo sapiens"


@pytest.mark.asyncio
async def test_resolve_target_returns_none_on_404():
    """A 404 response means the target doesn't exist — return None."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    resp.raise_for_status.return_value = None

    async def passthrough(fn, **kwargs):
        return await fn()

    with patch("integrations.chembl.with_retry", side_effect=passthrough):
        mock_client.get = AsyncMock(return_value=resp)
        result = await resolve_target(mock_client, "CHEMBL_NONEXISTENT")

    assert result is None


# ---------------------------------------------------------------------------
# get_targets_for_compounds — integration of the two functions above
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_targets_for_compounds_empty_list_returns_empty():
    """Empty compound list returns empty dict without HTTP calls."""
    result = await get_targets_for_compounds([])
    assert result == {}


@pytest.mark.asyncio
async def test_get_targets_for_compounds_returns_mapped_targets():
    """Returns dict mapping compound ChEMBL ID to list of ChemblTarget objects."""
    fake_bioactivity = ChemblBioactivity(
        molecule_chembl_id="CHEMBL_MOL_1",
        target_chembl_id="CHEMBL301",
        pchembl_value=7.5,
        target_organism="Homo sapiens",
        assay_type="B",
    )
    fake_target = ChemblTarget(
        chembl_id="CHEMBL301",
        gene_symbol="AKT1",
        uniprot_accession="P31749",
        organism="Homo sapiens",
        pchembl_value=None,
    )

    mock_client_instance = AsyncMock(spec=httpx.AsyncClient)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("integrations.chembl.get_bioactivities",
               AsyncMock(return_value=[fake_bioactivity])), \
         patch("integrations.chembl.resolve_target",
               AsyncMock(return_value=fake_target)), \
         patch("httpx.AsyncClient", return_value=mock_cm):
        result = await get_targets_for_compounds(["CHEMBL_MOL_1"])

    assert "CHEMBL_MOL_1" in result
    targets = result["CHEMBL_MOL_1"]
    assert len(targets) == 1
    assert targets[0].gene_symbol == "AKT1"
    assert targets[0].pchembl_value == pytest.approx(7.5)


@pytest.mark.asyncio
async def test_get_targets_for_compounds_deduplicates_same_gene():
    """Same gene_symbol from multiple activities appears only once per compound."""
    bioact1 = ChemblBioactivity(
        molecule_chembl_id="CHEMBL_MOL_1",
        target_chembl_id="CHEMBL301",
        pchembl_value=7.5,
        target_organism="Homo sapiens",
        assay_type="B",
    )
    bioact2 = ChemblBioactivity(
        molecule_chembl_id="CHEMBL_MOL_1",
        target_chembl_id="CHEMBL301",
        pchembl_value=8.0,
        target_organism="Homo sapiens",
        assay_type="B",
    )
    fake_target = ChemblTarget(
        chembl_id="CHEMBL301",
        gene_symbol="AKT1",
        uniprot_accession="P31749",
        organism="Homo sapiens",
        pchembl_value=None,
    )

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock(spec=httpx.AsyncClient))
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("integrations.chembl.get_bioactivities",
               AsyncMock(return_value=[bioact1, bioact2])), \
         patch("integrations.chembl.resolve_target",
               AsyncMock(return_value=fake_target)), \
         patch("httpx.AsyncClient", return_value=mock_cm):
        result = await get_targets_for_compounds(["CHEMBL_MOL_1"])

    # AKT1 should appear only once even though there were two bioactivities
    targets = result["CHEMBL_MOL_1"]
    gene_symbols = [t.gene_symbol for t in targets]
    assert gene_symbols.count("AKT1") == 1


@pytest.mark.asyncio
async def test_get_targets_for_compounds_raises_when_chembl_unavailable(httpx_mock):
    # Bioactivity fetch returns 503 on every attempt → ServiceUnavailableError
    # must propagate out of the gather instead of collapsing to empty targets.
    # with_retry default: max_retries=3 → 4 attempts per retried call.
    # 1 compound × 4 attempts = 4 total 503 responses consumed.
    for _ in range(4):
        httpx_mock.add_response(status_code=503)
    with pytest.raises(ServiceUnavailableError):
        await get_targets_for_compounds(["CHEMBL25"], min_pchembl=5.0)


@pytest.mark.asyncio
async def test_get_targets_for_compounds_does_not_share_cache_across_calls():
    """Each call builds a fresh target cache — no state leaks between runs.

    The internal target cache must be a per-call local, not a mutable default
    argument. If it leaked, a target resolved in one analysis run could
    cross-contaminate the compound→target evidence of an unrelated later run.
    This test resolves different targets on two consecutive calls and asserts
    the second call only sees its own target.
    """
    bioact_call1 = ChemblBioactivity(
        molecule_chembl_id="CHEMBL_MOL_1",
        target_chembl_id="CHEMBL301",
        pchembl_value=7.5,
        target_organism="Homo sapiens",
        assay_type="B",
    )
    target_call1 = ChemblTarget(
        chembl_id="CHEMBL301",
        gene_symbol="AKT1",
        uniprot_accession="P31749",
        organism="Homo sapiens",
        pchembl_value=None,
    )

    bioact_call2 = ChemblBioactivity(
        molecule_chembl_id="CHEMBL_MOL_2",
        target_chembl_id="CHEMBL999",
        pchembl_value=6.0,
        target_organism="Homo sapiens",
        assay_type="B",
    )
    target_call2 = ChemblTarget(
        chembl_id="CHEMBL999",
        gene_symbol="EGFR",
        uniprot_accession="P00533",
        organism="Homo sapiens",
        pchembl_value=None,
    )

    def _make_cm(client_instance):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client_instance)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    # Call 1: compound MOL_1 → AKT1 (CHEMBL301)
    with patch("integrations.chembl.get_bioactivities",
               AsyncMock(return_value=[bioact_call1])), \
         patch("integrations.chembl.resolve_target",
               AsyncMock(return_value=target_call1)), \
         patch("httpx.AsyncClient",
               return_value=_make_cm(AsyncMock(spec=httpx.AsyncClient))):
        result1 = await get_targets_for_compounds(["CHEMBL_MOL_1"])

    # Call 2: compound MOL_2 → EGFR (CHEMBL999). Crucially, the first call's
    # AKT1/CHEMBL301 target must NOT be visible to this fresh call.
    with patch("integrations.chembl.get_bioactivities",
               AsyncMock(return_value=[bioact_call2])), \
         patch("integrations.chembl.resolve_target",
               AsyncMock(return_value=target_call2)), \
         patch("httpx.AsyncClient",
               return_value=_make_cm(AsyncMock(spec=httpx.AsyncClient))):
        result2 = await get_targets_for_compounds(["CHEMBL_MOL_2"])

    assert [t.gene_symbol for t in result1["CHEMBL_MOL_1"]] == ["AKT1"]
    # The second call sees only EGFR — no leaked AKT1 from the first call's cache.
    call2_genes = [t.gene_symbol for t in result2["CHEMBL_MOL_2"]]
    assert call2_genes == ["EGFR"]
    assert "AKT1" not in call2_genes
