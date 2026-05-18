-- Adds ADME columns that the lipinski ETL patch computed but may not be in DB schema.
-- IF NOT EXISTS is safe to run repeatedly.

ALTER TABLE compounds
  ADD COLUMN IF NOT EXISTS rotatable_bonds    integer,
  ADD COLUMN IF NOT EXISTS num_ro5_violations integer,
  ADD COLUMN IF NOT EXISTS qed_score          float,
  ADD COLUMN IF NOT EXISTS np_likeness_score  float,
  ADD COLUMN IF NOT EXISTS lipinski_source    text;
