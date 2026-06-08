from datetime import UTC

from app.clock import now_utc


def test_now_utc_is_timezone_aware() -> None:
    value = now_utc()
    assert value.tzinfo is not None
    assert value.utcoffset() == UTC.utcoffset(None)
