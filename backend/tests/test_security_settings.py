"""Regression guard: CORS origins are an explicit allowlist, never a wildcard."""

from app.config import Settings


def test_cors_origins_are_an_allowlist_not_wildcard() -> None:
    s = Settings()
    origins = s.cors_origins_list
    assert origins  # non-empty
    assert "*" not in origins  # never a wildcard origin
