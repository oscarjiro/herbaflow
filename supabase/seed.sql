-- Reference data only — no entity data here.

insert into source_systems (source_name, source_type, base_url, notes) values
  ('KNApSAcK World',       'scrape',   'https://www.knapsackfamily.com/KNApSAcK_World',   'Indonesian medicinal plant-compound database'),
  ('GBIF',                 'api',      'https://api.gbif.org/v1/',                 'Global Biodiversity Information Facility — taxonomy authority'),
  ('PubChem',              'api',      'https://pubchem.ncbi.nlm.nih.gov/',        'NCBI compound structure and property database'),
  ('ChEMBL',               'api',      'https://www.ebi.ac.uk/chembl/',            'Bioactive compound and bioactivity database'),
  ('OpenTargets',          'api',      'https://api.platform.opentargets.org/',    'Target-disease associations via GraphQL'),
  ('UniProt',              'api',      'https://www.uniprot.org/',                 'Protein sequence and function authority (UniProtKB accessions)'),
  ('Disease Ontology',     'download', 'https://disease-ontology.org/',            'Standardized disease ontology (DOID)'),
  ('curated_disease_seed', 'manual',   null,                                       'Hand-curated initial disease seed list')
on conflict (source_name) do nothing;
