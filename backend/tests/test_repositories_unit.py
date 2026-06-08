from datetime import timedelta

from app.clock import now_utc
from app.repositories.analysis import expires_after


def test_expires_after_is_24h() -> None:
    base = now_utc()
    assert expires_after(base) == base + timedelta(hours=24)
