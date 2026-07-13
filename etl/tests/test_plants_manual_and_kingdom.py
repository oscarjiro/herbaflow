"""Regression tests for the plants ETL audit fixes (2026-07-13).

Covers:
- kingdom filter: non-Plantae GBIF matches (fungi) are rejected in build_canonical part 1;
- manual-review merge: a curator-resolved species is folded into the final plants seed;
- accepted-name-over-synonym: resolve_manual_reviews stores the accepted name + accepted key;
- manual-file preservation: part 1 no longer wipes a populated manually_accepted file;
- non-ASCII names round-trip without mojibake (U+FFFD).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ETL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ETL))


def _load(mod_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(mod_name, ETL / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod  # register before exec so @dataclass resolves
    spec.loader.exec_module(mod)
    return mod


part1 = _load("plants_build_part1", "plants/04_build_canonical/run_part1.py")
part2 = _load("plants_build_part2", "plants/04_build_canonical/run_part2.py")
resolve = _load("plants_resolve_manual", "plants/04_build_canonical/resolve_manual_reviews.py")

from shared.identity import plant_canonical_key
from shared.identity import plant_id as make_plant_id


def _match_row(**overrides) -> pd.Series:
    base = {
        "query_status": "ok",
        "match_type": "EXACT",
        "taxonomic_status": "ACCEPTED",
        "confidence": "99",
        "matched_name": "Some plant",
        "accepted_name": "Some plant",
        "http_status": "200",
        "error_message": "",
        "gbif_kingdom_key": "6",
    }
    base.update(overrides)
    return pd.Series(base)


# --- Defect 2: kingdom filter -------------------------------------------------


def test_fungus_kingdom_key_is_rejected():
    # Ganoderma lucidum resolves to kingdom Fungi (key 5) at EXACT/confidence 99.
    row = _match_row(
        matched_name="Ganoderma lucidum",
        accepted_name="Ganoderma lucidum",
        gbif_kingdom_key="5",
    )
    decision, reason = part1.determine_decision(row)
    assert decision == "rejected"
    assert "kingdom" in reason.lower()


def test_plant_kingdom_key_is_accepted():
    row = _match_row(gbif_kingdom_key="6")
    decision, _ = part1.determine_decision(row)
    assert decision == "accepted"


def test_missing_kingdom_key_not_rejected_by_kingdom_guard():
    # Empty kingdom key must not cause a false rejection; normal rules still apply.
    row = _match_row(gbif_kingdom_key="")
    decision, _ = part1.determine_decision(row)
    assert decision == "accepted"


def test_plantae_kingdom_key_constant_is_six():
    assert part1.PLANTAE_KINGDOM_KEY == "6"


# --- Defect 3: accepted-name over synonym in the manual path ------------------


def _caesalpinia_gbif() -> dict:
    # Shape of a real GBIF /v1/species/{key} response for a synonym usage key.
    return {
        "key": 8179846,
        "scientificName": "Caesalpinia crista L.",
        "authorship": "L.",
        "accepted": "Ticanto crista (L.) R.Clark & Gagnon",
        "acceptedKey": 11973078,
        "acceptedUsageKey": None,
        "taxonomicStatus": "SYNONYM",
        "rank": "SPECIES",
        "family": "Fabaceae",
        "familyKey": 5386,
        "genusKey": 2958443,
        "speciesKey": 11973078,
        "kingdomKey": 6,
    }


def test_resolved_row_uses_accepted_name_and_accepted_key():
    row = resolve.build_resolved_row(
        _caesalpinia_gbif(), "Caesalpinia crista", "83", "KNApSAcK World"
    )
    # Canonical name is the ACCEPTED name, not the chosen synonym's own name.
    assert row["canonical_scientific_name"] == "Ticanto crista (L.) R.Clark & Gagnon"
    assert row["accepted_name"] == "Ticanto crista (L.) R.Clark & Gagnon"
    # Own name retained for the synonym alias.
    assert row["matched_name"] == "Caesalpinia crista L."
    # Identity key points at the ACCEPTED taxon (v1 acceptedKey), not the synonym key.
    assert str(row["gbif_accepted_usage_key"]) == "11973078"
    assert row["family_name"] == "Fabaceae"
    assert str(row["gbif_kingdom_key"]) == "6"


def test_resolved_row_accepted_taxon_uses_own_name():
    data = {
        "key": 3086358,
        "scientificName": "Piper methysticum G.Forst.",
        "authorship": "G.Forst.",
        "taxonomicStatus": "ACCEPTED",
        "rank": "SPECIES",
        "family": "Piperaceae",
        "kingdomKey": 6,
    }
    row = resolve.build_resolved_row(data, "Piper methysticum", "398", "KNApSAcK World")
    assert row["canonical_scientific_name"] == "Piper methysticum G.Forst."
    assert str(row["gbif_accepted_usage_key"]) == "3086358"


# --- Defect 4: non-ASCII names round-trip without mojibake --------------------


def test_hybrid_and_diacritic_names_have_no_replacement_char():
    data = {
        "key": 3190173,
        "scientificName": "Citrus ×nobilis Lour.",  # U+00D7 multiplication sign
        "accepted": "Meistera aculeata (Roxb.) Škor",  # U+0160 latin S caron
        "taxonomicStatus": "SYNONYM",
        "acceptedKey": 999,
        "family": "Rutaceae",
        "kingdomKey": 6,
    }
    row = resolve.build_resolved_row(data, "Citrus nobilis", "130", "KNApSAcK World")
    assert "�" not in row["canonical_scientific_name"]
    assert "Š" in row["canonical_scientific_name"]
    assert "×" in row["matched_name"]


# --- Defect 1: manual merge and file preservation ----------------------------

_ACCEPTED_COLUMNS = [
    "decision",
    "decision_reason",
    "source_name",
    "canonical_scientific_name",
    "authorship",
    "input_name",
    "raw_plant_id",
    "canonical_lookup_key",
    "source_row_count",
    "query_status",
    "http_status",
    "error_message",
    "matched_name",
    "accepted_name",
    "rank",
    "taxonomic_status",
    "match_type",
    "confidence",
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
    "family_name",
    "cache_key",
    "cache_path",
]


def _accepted_row(**over) -> dict:
    row = {c: "" for c in _ACCEPTED_COLUMNS}
    row.update(
        decision="accepted",
        source_name="KNApSAcK World",
        source_row_count="1",
        query_status="ok",
        http_status="200",
        match_type="EXACT",
        confidence="99",
        taxonomic_status="ACCEPTED",
        gbif_kingdom_key="6",
    )
    row.update(over)
    return row


def test_manual_review_species_merges_into_plants(tmp_path):
    out = tmp_path
    accepted = pd.DataFrame(
        [
            _accepted_row(
                canonical_scientific_name="Andrographis paniculata (Burm.f.) Nees",
                matched_name="Andrographis paniculata (Burm.f.) Nees",
                accepted_name="Andrographis paniculata (Burm.f.) Nees",
                raw_plant_id="1",
                gbif_usage_key="2925303",
                gbif_accepted_usage_key="2925303",
                family_name="Acanthaceae",
            )
        ]
    )
    accepted_path = out / "accepted_plants.csv"
    accepted.to_csv(accepted_path, index=False, encoding="utf-8")

    manual_row = resolve.build_resolved_row(
        _caesalpinia_gbif(), "Caesalpinia crista", "83", "KNApSAcK World"
    )
    manual_path = out / "manually_accepted_review_plants.csv"
    pd.DataFrame([manual_row], columns=resolve.RESOLVED_COLUMNS).to_csv(
        manual_path, index=False, encoding="utf-8"
    )

    result = part2.build_seed_files(
        input_path=accepted_path,
        manually_accepted_review_path=manual_path,
        output_dir=out,
        plants_file="plants.csv",
        aliases_file="plant_aliases.csv",
        report_file="report.txt",
        source_name_fallback="KNApSAcK World",
    )

    plants = pd.read_csv(out / "plants.csv", dtype=str, keep_default_na=False)
    names = set(plants["canonical_scientific_name"])
    assert "Ticanto crista (L.) R.Clark & Gagnon" in names
    assert "Andrographis paniculata (Burm.f.) Nees" in names
    assert result.plant_rows == 2

    # The merged plant's identity is built off the ACCEPTED usage key.
    expected_key = plant_canonical_key("11973078", "Ticanto crista (L.) R.Clark & Gagnon")
    expected_id = make_plant_id("11973078", "Ticanto crista (L.) R.Clark & Gagnon")
    merged = plants[plants["canonical_scientific_name"].str.startswith("Ticanto")].iloc[0]
    assert merged["canonical_key"] == expected_key
    assert merged["plant_id"] == expected_id

    # The curator's original spelling survives as a synonym alias.
    aliases = pd.read_csv(out / "plant_aliases.csv", dtype=str, keep_default_na=False)
    syn = aliases[aliases["plant_id"] == expected_id]["alias_name"].tolist()
    assert any("Caesalpinia crista" in a for a in syn)


def test_part1_preserves_populated_manual_file(tmp_path):
    out = tmp_path
    # Minimal GBIF match input for part 1 (one accepted plant).
    matches = pd.DataFrame(
        [
            {
                "input_name": "Andrographis paniculata",
                "raw_plant_id": "1",
                "canonical_lookup_key": "andrographis paniculata",
                "source_row_count": "1",
                "query_status": "ok",
                "http_status": "200",
                "error_message": "",
                "matched_name": "Andrographis paniculata (Burm.f.) Nees",
                "accepted_name": "Andrographis paniculata (Burm.f.) Nees",
                "authorship": "(Burm.f.) Nees",
                "rank": "SPECIES",
                "taxonomic_status": "ACCEPTED",
                "match_type": "EXACT",
                "confidence": "99",
                "gbif_usage_key": "2925303",
                "gbif_accepted_usage_key": "2925303",
                "gbif_species_key": "2925303",
                "gbif_genus_key": "",
                "gbif_family_key": "",
                "gbif_kingdom_key": "6",
                "family_name": "Acanthaceae",
                "cache_key": "x",
                "cache_path": "y",
            }
        ]
    )
    input_path = out / "gbif_matches.csv"
    matches.to_csv(input_path, index=False, encoding="utf-8")

    # A populated manual file already exists on disk (simulating curator work).
    manual_path = out / "manually_accepted_review_plants.csv"
    populated = pd.DataFrame([{"input_name": "Piper methysticum", "raw_plant_id": "398"}])
    populated.to_csv(manual_path, index=False, encoding="utf-8")

    part1.build_canonical(
        input_path=input_path,
        output_dir=out,
        accepted_file="accepted_plants.csv",
        review_file="review_plants.csv",
        rejected_file="rejected_plants.csv",
        manually_accepted_review_file="manually_accepted_review_plants.csv",
        report_file="report.txt",
        source_name="KNApSAcK World",
    )

    after = pd.read_csv(manual_path, dtype=str, keep_default_na=False)
    # The populated file must NOT be wiped.
    assert len(after) == 1
    assert after.iloc[0]["input_name"] == "Piper methysticum"
