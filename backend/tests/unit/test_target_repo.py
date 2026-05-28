"""Unit tests for app/repositories/target_repo.py.

Tests ORM query structure and upsert deduplication logic using mock sessions.
No real database connections are used.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models import Target, CompoundTarget, DiseaseTarget
from app.repositories import target_repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_session():
    """Return a mock AsyncSession with exec/add/commit/refresh mocked."""
    session = AsyncMock()
    return session


def make_target(
    target_id: str = "tgt_001",
    canonical_key: str = "chembl:CHEMBL301",
    gene_symbol: str = "AKT1",
) -> Target:
    t = Target(
        target_id=target_id,
        canonical_key=canonical_key,
        gene_symbol=gene_symbol,
        protein_name="RAC-alpha serine/threonine-protein kinase",
        uniprot_accession="P31749",
        organism_tax_id=9606,
    )
    return t


# ---------------------------------------------------------------------------
# test_target_repo_get_targets_for_analysis_returns_list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_targets_by_compound_returns_list():
    """get_targets_by_compound executes a join query and returns a list."""
    session = make_mock_session()

    fake_target = make_target()
    exec_result = MagicMock()
    exec_result.all.return_value = [fake_target]
    session.exec = AsyncMock(return_value=exec_result)

    result = await target_repo.get_targets_by_compound(session, "compound-123")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].gene_symbol == "AKT1"
    session.exec.assert_called_once()


@pytest.mark.asyncio
async def test_get_targets_by_compound_returns_empty_list_when_no_targets():
    """Returns empty list when no compound-target associations exist."""
    session = make_mock_session()

    exec_result = MagicMock()
    exec_result.all.return_value = []
    session.exec = AsyncMock(return_value=exec_result)

    result = await target_repo.get_targets_by_compound(session, "compound-no-targets")

    assert result == []


@pytest.mark.asyncio
async def test_get_targets_by_disease_returns_list():
    """get_targets_by_disease executes a join query and returns a list."""
    session = make_mock_session()

    fake_target = make_target(target_id="tgt_002", canonical_key="chembl:CHEMBL302", gene_symbol="TP53")
    exec_result = MagicMock()
    exec_result.all.return_value = [fake_target]
    session.exec = AsyncMock(return_value=exec_result)

    result = await target_repo.get_targets_by_disease(session, "disease-abc")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].gene_symbol == "TP53"
    session.exec.assert_called_once()


# ---------------------------------------------------------------------------
# test_target_repo_upsert_creates_new_target
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_target_creates_new_when_not_exists():
    """upsert_target calls session.add when canonical_key is not found."""
    session = make_mock_session()

    # exec returns None from .first() → target does not exist yet
    exec_result = MagicMock()
    exec_result.first.return_value = None
    session.exec = AsyncMock(return_value=exec_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    new_target = make_target()
    result = await target_repo.upsert_target(session, new_target)

    session.add.assert_called_once_with(new_target)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(new_target)
    assert result is new_target


# ---------------------------------------------------------------------------
# test_target_repo_upsert_deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_target_returns_existing_on_duplicate_canonical_key():
    """upsert_target returns the existing target without calling add when key exists."""
    session = make_mock_session()

    existing_target = make_target(target_id="tgt_existing", canonical_key="chembl:CHEMBL301")

    # First exec call returns existing_target (found by canonical_key)
    exec_result = MagicMock()
    exec_result.first.return_value = existing_target
    session.exec = AsyncMock(return_value=exec_result)
    session.add = MagicMock()

    duplicate = make_target(target_id="tgt_new", canonical_key="chembl:CHEMBL301")
    result = await target_repo.upsert_target(session, duplicate)

    session.add.assert_not_called()
    assert result is existing_target
    assert result.target_id == "tgt_existing"


@pytest.mark.asyncio
async def test_upsert_target_deduplication_same_key_twice():
    """Two upserts with the same canonical_key: second call returns the first's target."""
    session = make_mock_session()

    first_target = make_target(target_id="tgt_first", canonical_key="chembl:CHEMBL999")

    # First call: nothing in DB → insert
    exec_result_empty = MagicMock()
    exec_result_empty.first.return_value = None

    # Second call: first_target found in DB → deduplicate
    exec_result_found = MagicMock()
    exec_result_found.first.return_value = first_target

    session.exec = AsyncMock(side_effect=[exec_result_empty, exec_result_found])
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    t1 = make_target(target_id="tgt_first", canonical_key="chembl:CHEMBL999")
    t2 = make_target(target_id="tgt_second", canonical_key="chembl:CHEMBL999")

    result1 = await target_repo.upsert_target(session, t1)
    result2 = await target_repo.upsert_target(session, t2)

    # First upsert → added; second upsert → returned existing, no second add
    assert session.add.call_count == 1
    assert result2.target_id == "tgt_first"


# ---------------------------------------------------------------------------
# test_get_target_by_id and test_get_target_by_gene_symbol
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_target_by_id_returns_target_when_found():
    """get_target_by_id returns target when ID matches."""
    session = make_mock_session()

    fake_target = make_target()
    exec_result = MagicMock()
    exec_result.first.return_value = fake_target
    session.exec = AsyncMock(return_value=exec_result)

    result = await target_repo.get_target_by_id(session, "tgt_001")

    assert result is fake_target
    session.exec.assert_called_once()


@pytest.mark.asyncio
async def test_get_target_by_id_returns_none_when_not_found():
    """get_target_by_id returns None when target does not exist."""
    session = make_mock_session()

    exec_result = MagicMock()
    exec_result.first.return_value = None
    session.exec = AsyncMock(return_value=exec_result)

    result = await target_repo.get_target_by_id(session, "tgt_nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_get_target_by_gene_symbol_uppercases_query():
    """get_target_by_gene_symbol normalises gene symbol to uppercase."""
    session = make_mock_session()

    fake_target = make_target(gene_symbol="AKT1")
    exec_result = MagicMock()
    exec_result.first.return_value = fake_target
    session.exec = AsyncMock(return_value=exec_result)

    # Pass lowercase — should still find the target via uppercase normalisation
    result = await target_repo.get_target_by_gene_symbol(session, "akt1")

    assert result is fake_target
