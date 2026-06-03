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


STAGE_LABELS = {
    1: "Compound selection",
    2: "ADME prediction",
    3: "Target identification",
    4: "Disease-target mapping",
    5: "Target overlap",
    6: "PPI network construction",
    7: "Hub-gene analysis",
    8: "Pathway enrichment",
}


def client_error_message(stage_num: int) -> str:
    """A plain, non-technical failure message safe to show anonymous clients.

    The full traceback is logged server-side; this NEVER includes exception
    classes, file paths, or stack frames.
    """
    label = STAGE_LABELS.get(stage_num, "Pipeline")
    return (
        f"{label} (stage {stage_num}) could not be completed, so the analysis "
        f"was stopped at this step. Please try again or adjust your inputs."
    )
