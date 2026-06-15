"""Guard: user-facing display copy in the contract must contain no internal jargon or dashes.

Banned substrings (per project policy):
- § (section sign used in internal citations)
- "Lock" (as in Methodology Lock / Software Lock)
- "ETL" (internal pipeline term)
- em dash — (U+2014)
- en dash – (U+2013)
"""

import pytest

from app import contracts

_BANNED = ["§", "Lock", "ETL", "—", "–"]

_PARAM_GROUPS = ["adme", "target", "disease_targets", "ppi", "hub_genes", "enrichment"]
_COMPUTED_STAGES = [1, 2, 3, 4, 5, 6, 7, 8]


def _check_no_banned(text: str, location: str) -> None:
    for substr in _BANNED:
        assert substr not in text, f"Banned substring {substr!r} found in {location}: {text!r}"


@pytest.mark.parametrize("stage", _COMPUTED_STAGES)
def test_stage_sources_computed_names_clean(stage: int) -> None:
    for entry in contracts.stage_sources(stage, user_provided=False):
        name: str = entry["name"] or ""
        _check_no_banned(name, f"stage_sources computed stage={stage} name")


@pytest.mark.parametrize("stage", [1, 3, 4])
def test_stage_sources_user_provided_names_clean(stage: int) -> None:
    for entry in contracts.stage_sources(stage, user_provided=True):
        name = entry["name"] or ""
        _check_no_banned(name, f"stage_sources user_provided stage={stage} name")


@pytest.mark.parametrize("group", _PARAM_GROUPS)
def test_param_descriptions_clean(group: str) -> None:
    bounds = contracts.pipeline_param_bounds(group)
    for param_key, spec in bounds.items():
        desc = spec.get("description")
        if desc:
            location = f"pipeline_param_bounds group={group} param={param_key} description"
            _check_no_banned(desc, location)
