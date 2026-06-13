-- Record the Stage-3 discovery thresholds on each measured edge so a later run can soundly
-- decide reuse vs refetch (min_assay_confidence is not otherwise re-derivable from the edge). D9.
alter table compound_targets add column min_pchembl double precision;
alter table compound_targets add column min_assay_confidence integer;
