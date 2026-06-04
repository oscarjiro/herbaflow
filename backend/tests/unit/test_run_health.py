from analysis.run_health import derive_run_health


def test_clean_complete_run_has_results_not_degraded():
    sr = {"stage_3": {"target_count": 12}}
    h = derive_run_health(sr, "complete")
    assert h == {"warnings": [], "degraded": False, "has_results": True, "retriable": False}


def test_empty_critical_spine_sets_has_results_false():
    sr = {"stage_3": {"target_count": 0}}
    h = derive_run_health(sr, "complete")
    assert h["has_results"] is False
    assert h["degraded"] is False


def test_degraded_stage_collects_warning():
    sr = {"stage_3": {"target_count": 5},
          "stage_8": {"degraded": True, "warning": {"provider": "g:Profiler", "reason": "down"}}}
    h = derive_run_health(sr, "complete")
    assert h["degraded"] is True
    assert h["warnings"] == [{"stage": 8, "provider": "g:Profiler", "reason": "down"}]


def test_retriable_only_for_provider_and_timeout_kinds():
    base = {"stage_3": {"target_count": 0}}
    assert derive_run_health({**base, "_run_health": {"failure_kind": "provider_unavailable"}}, "failed")["retriable"] is True
    assert derive_run_health({**base, "_run_health": {"failure_kind": "timeout"}}, "failed")["retriable"] is True
    assert derive_run_health({**base, "_run_health": {"failure_kind": "internal_error"}}, "failed")["retriable"] is False
    assert derive_run_health(base, "complete")["retriable"] is False


def test_manual_targets_mode_uses_stage4_for_has_results():
    sr = {"stage_4": {"disease_target_count": 3}}
    assert derive_run_health(sr, "complete")["has_results"] is True
    sr2 = {"stage_4": {"disease_target_count": 0}}
    assert derive_run_health(sr2, "complete")["has_results"] is False
