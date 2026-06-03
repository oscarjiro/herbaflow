"""Security helpers: filename sanitization, safe error messages, rate limiter,
and a request payload-size middleware. Wave 4 hardening.
"""
import re

# Anything outside this conservative set is replaced. Note: '.' is allowed so
# file extensions survive; path separators, quotes, control chars, and CR/LF
# (header-injection vectors) are all stripped.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, *, default: str = "analysis", max_len: int = 128) -> str:
    """Return an ASCII-only, header-safe filename stem.

    Drops non-ASCII, collapses runs of unsafe chars to '_', trims surrounding
    dots/spaces/underscores, falls back to ``default`` if nothing remains, and
    caps length to keep the Content-Disposition header bounded.
    """
    ascii_only = name.encode("ascii", "ignore").decode("ascii")
    cleaned = _UNSAFE.sub("_", ascii_only).strip(" ._")
    if not cleaned:
        cleaned = default
    return cleaned[:max_len]
