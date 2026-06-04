"""Guards the timezone-aware UTC standardization.

Postgres timestamptz columns return tz-AWARE datetimes on read via asyncpg.
Minting naive datetimes (datetime.utcnow) and comparing them against those
aware values raises TypeError -> HTTP 500. now_utc() must always be aware.
"""

from datetime import timezone

from app.repositories.analysis_repo import now_utc


def test_now_utc_is_timezone_aware():
    n = now_utc()
    assert n.tzinfo is not None
    assert n.utcoffset() == timezone.utc.utcoffset(None)
