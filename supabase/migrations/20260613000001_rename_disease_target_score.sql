-- Rename disease_targets.score -> opentargets_score (it is the Open Targets overall
-- association score, not a generic/cross-source score). Provenance-honest naming (H-1).
alter table disease_targets rename column score to opentargets_score;
