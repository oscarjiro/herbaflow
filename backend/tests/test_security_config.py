from app.config import Settings


def test_security_settings_have_safe_defaults():
    s = Settings()
    assert s.max_request_bytes == 1_048_576
    assert s.rate_limit_enabled is True
    assert s.rate_limit_default == "120/minute"
    assert s.rate_limit_create == "5/minute"
    assert s.rate_limit_validate == "20/minute"
