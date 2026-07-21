"""Guard: the integration schema must not drift behind the migrations on disk.

The fixture applies a hand-maintained list of migrations. When a new migration was added and the
list was not updated, the test database silently stayed a schema version behind the ORM and the
whole integration suite failed with ``column compounds.source_name does not exist``.

This test makes that failure mode impossible to reintroduce quietly: every ``.sql`` file in
``supabase/migrations`` must be classified as either applied or deliberately skipped.
"""

from __future__ import annotations

from .conftest import _APPLY, _MIGRATIONS, _SKIP


def test_every_migration_is_classified() -> None:
    on_disk = {p.name for p in _MIGRATIONS.glob("*.sql")}
    classified = set(_APPLY) | set(_SKIP)

    unclassified = sorted(on_disk - classified)
    assert not unclassified, (
        "migration(s) on disk are neither applied nor skipped by the integration fixture: "
        f"{unclassified}. Add each to _APPLY (if the slice needs the schema change) or to "
        "_SKIP (with the reason it cannot run on a vanilla Postgres image)."
    )


def test_no_phantom_migrations_listed() -> None:
    on_disk = {p.name for p in _MIGRATIONS.glob("*.sql")}
    missing = sorted((set(_APPLY) | set(_SKIP)) - on_disk)
    assert not missing, f"listed migration(s) do not exist on disk: {missing}"


def test_apply_and_skip_are_disjoint() -> None:
    both = sorted(set(_APPLY) & set(_SKIP))
    assert not both, f"migration(s) listed as both applied and skipped: {both}"
