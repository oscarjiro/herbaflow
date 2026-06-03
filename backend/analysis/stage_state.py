"""Canonical per-stage `state` values. Mirrors shared/contracts/analysis.json
("stage_state") — test_stage_state_contract guards drift."""

COMPUTED = "computed"
USER_PROVIDED = "user_provided"
NOT_APPLICABLE = "not_applicable"

ALL: tuple[str, ...] = (COMPUTED, USER_PROVIDED, NOT_APPLICABLE)
