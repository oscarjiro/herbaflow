"""Run-level health signals derived from stage_results + status.

No new DB columns: per-stage markers live in stage_results JSONB and the
failure-kind marker in stage_results["_run_health"]. These functions compute the
run-level view at response time.
"""

_RETRIABLE_KINDS = {"provider_unavailable", "timeout"}


def _collect_warnings(stage_results: dict) -> list[dict]:
    warnings: list[dict] = []
    for key, val in stage_results.items():
        if not key.startswith("stage_") or not isinstance(val, dict):
            continue
        warning = val.get("warning")
        if val.get("degraded") and isinstance(warning, dict):
            try:
                stage_num = int(key.split("_")[1])
            except (IndexError, ValueError):
                continue
            warnings.append({
                "stage": stage_num,
                "provider": warning.get("provider", ""),
                "reason": warning.get("reason", ""),
            })
    return sorted(warnings, key=lambda w: w["stage"])


def _has_results(stage_results: dict) -> bool:
    s3 = stage_results.get("stage_3")
    if isinstance(s3, dict):
        return (s3.get("target_count") or 0) > 0
    s4 = stage_results.get("stage_4")
    if isinstance(s4, dict):
        return (s4.get("disease_target_count") or 0) > 0
    return True


def _retriable(stage_results: dict, status: str) -> bool:
    if status != "failed":
        return False
    kind = (stage_results.get("_run_health") or {}).get("failure_kind")
    return kind in _RETRIABLE_KINDS


def derive_run_health(stage_results: dict, status: str) -> dict:
    stage_results = stage_results or {}
    warnings = _collect_warnings(stage_results)
    return {
        "warnings": warnings,
        "degraded": len(warnings) > 0,
        "has_results": _has_results(stage_results),
        "retriable": _retriable(stage_results, status),
    }
