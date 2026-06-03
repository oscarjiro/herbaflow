import os
from importlib import reload

import app.config as config_module


def _fresh_settings(**env):
    """Build a Settings instance with a patched environment (bypasses lru_cache)."""
    old = dict(os.environ)
    os.environ.update({k: str(v) for k, v in env.items()})
    try:
        reload(config_module)
        return config_module.Settings()
    finally:
        os.environ.clear()
        os.environ.update(old)
        reload(config_module)


def test_cors_defaults_to_dev_origins():
    s = _fresh_settings(DATABASE_URL="postgresql://x")
    assert s.cors_origin_list == ["http://localhost:5173", "http://localhost:3000"]


def test_cors_origins_env_override_is_split_and_trimmed():
    s = _fresh_settings(DATABASE_URL="postgresql://x", CORS_ORIGINS="https://a.com, https://b.com")
    assert s.cors_origin_list == ["https://a.com", "https://b.com"]


def test_rate_limit_and_payload_defaults():
    s = _fresh_settings(DATABASE_URL="postgresql://x")
    assert s.rate_limit_enabled is True
    assert s.rate_limit_default == "120/minute"
    assert s.rate_limit_create == "10/minute"
    assert s.rate_limit_export == "30/minute"
    assert s.max_request_bytes == 2_097_152
