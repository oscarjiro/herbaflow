-- Seeds provenance rows for Stage-3 target sources that are not yet registered.
-- ChEMBL, UniProt and PubChem already exist in source_systems; only the
-- distinct PubChem BioAssay screening source and the user-pasted
-- SwissTargetPrediction import source are added here. Idempotent.

insert into public.source_systems (source_id, source_name, source_type, base_url, notes)
values
  (gen_random_uuid(), 'PubChem BioAssay', 'api', 'https://pubchem.ncbi.nlm.nih.gov/',
   'Deposited bioassay screening outcomes (active calls) for compound-target edges.'),
  (gen_random_uuid(), 'SwissTargetPrediction', 'manual', 'http://www.swisstargetprediction.ch/',
   'User-run target prediction, pasted back into a run (stp_import edges).')
on conflict (source_name) do nothing;
