import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

const BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Shared fixture data
// ---------------------------------------------------------------------------

const ADME_FROZEN_DEFAULTS = {
  max_mw: 500,
  max_logp: 5,
  max_hbd: 5,
  max_hba: 10,
  max_tpsa: 140,
  max_rotatable_bonds: 10,
  apply_veber: true,
  np_exception_threshold: 0.5,
  apply_np_exception: true,
  max_violations: 1,
  skip_adme: false,
};

export const SAMPLE_STAGE2_RESULTS = {
  count: 3,
  state: "computed",
  passed: [
    {
      compound_id: "c1",
      canonical_name: "Curcumin",
      descriptor_source: "rdkit",
      molecular_weight: 368.4,
      logp: 3.2,
      hbond_donors: 2,
      hbond_acceptors: 6,
      tpsa: 93.1,
      rotatable_bonds: 8,
      qed_score: 0.55,
      np_likeness_score: 1.8,
      num_ro5_violations: 0,
      is_pains_positive: true,
      source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/969516",
      badges: ["pains"],
    },
    {
      compound_id: "c2",
      canonical_name: "Berberine",
      descriptor_source: "etl",
      molecular_weight: 336.4,
      logp: 1.3,
      hbond_donors: 0,
      hbond_acceptors: 4,
      tpsa: 40.8,
      rotatable_bonds: 1,
      qed_score: 0.49,
      np_likeness_score: 2.1,
      num_ro5_violations: 0,
      is_pains_positive: false,
      source_url: null,
      badges: ["np_bypass"],
    },
  ],
  filtered: [
    {
      compound_id: "c3",
      canonical_name: "HeavyMolecule",
      descriptor_source: "rdkit",
      molecular_weight: 850.2,
      logp: 8.5,
      hbond_donors: 3,
      hbond_acceptors: 8,
      tpsa: 120.0,
      rotatable_bonds: 12,
      qed_score: 0.12,
      np_likeness_score: -1.0,
      num_ro5_violations: 3,
      is_pains_positive: false,
      source_url: null,
      badges: [],
      reason: "Exceeds max_mw (850.2 > 500)",
    },
  ],
  annotations: {
    pains: ["c1"],
    np_bypass: ["c2"],
    unscreened: [],
    could_not_screen: [],
  },
};

// r3: stage_1_awaiting_approval — tagged compounds for Step-1 editor tests
export const ANALYSIS_STAGE1_AWAITING = {
  analysis_id: "r3",
  analysis_name: null,
  disease_id: "d1",
  mode: "guided",
  status: "stage_1_awaiting_approval",
  current_stage: 1,
  parameters: { adme: ADME_FROZEN_DEFAULTS },
  stage_results: {
    "1": {
      count: 2,
      compounds: [
        { compound_id: "c1", canonical_name: "Curcumin", tag: "computed" },
        { compound_id: "c2", canonical_name: "Berberine", tag: "user-added" },
        { compound_id: "c3", canonical_name: "RemovedOne", tag: "user-removed" },
      ],
      per_plant: {},
      state: "user_provided",
    },
  },
  created_at: null,
  completed_at: null,
  expires_at: null,
  error_message: null,
};

// r4: stage_1_awaiting_approval — count at cap (2000) to test disabled add
export const ANALYSIS_STAGE1_AT_CAP = {
  analysis_id: "r4",
  analysis_name: null,
  disease_id: "d1",
  mode: "guided",
  status: "stage_1_awaiting_approval",
  current_stage: 1,
  parameters: { adme: ADME_FROZEN_DEFAULTS },
  stage_results: {
    "1": {
      count: 2000,
      compounds: [{ compound_id: "c1", canonical_name: "Curcumin", tag: "computed" }],
      per_plant: {},
      state: "computed",
    },
  },
  created_at: null,
  completed_at: null,
  expires_at: null,
  error_message: null,
};

const ANALYSIS_WITH_STAGE2 = {
  analysis_id: "r2",
  analysis_name: null,
  disease_id: "d1",
  mode: "guided",
  status: "stage_2_awaiting_approval",
  current_stage: 2,
  parameters: {
    adme: ADME_FROZEN_DEFAULTS,
  },
  stage_results: {
    "1": {
      count: 3,
      compounds: [
        { compound_id: "c1", canonical_name: "Curcumin" },
        { compound_id: "c2", canonical_name: "Berberine" },
        { compound_id: "c3", canonical_name: "HeavyMolecule" },
      ],
      per_plant: {},
      state: "computed",
    },
    "2": SAMPLE_STAGE2_RESULTS,
  },
  created_at: null,
  completed_at: null,
  expires_at: null,
  error_message: null,
};

export const server = setupServer(
  http.get(`${BASE}/diseases`, () =>
    HttpResponse.json([
      {
        disease_id: "d1",
        canonical_key: "doid:1",
        disease_name: "Test Disease",
        ontology_id: null,
        ontology_source: null,
        source_url: null,
        retrieved_at: null,
      },
    ]),
  ),
  http.get(`${BASE}/plants`, () =>
    HttpResponse.json([
      {
        plant_id: "p1",
        canonical_key: "gbif:1",
        canonical_scientific_name: "Aaa bbb",
        family_name: null,
      },
    ]),
  ),
  http.post(`${BASE}/analyses`, () =>
    HttpResponse.json(
      {
        analysis_id: "r1",
        analysis_name: null,
        disease_id: "d1",
        mode: "auto",
        status: "pending",
        current_stage: null,
        stage_results: {},
        created_at: null,
        completed_at: null,
        expires_at: null,
        error_message: null,
      },
      { status: 202 },
    ),
  ),
  http.post(`${BASE}/compounds/validate`, () =>
    HttpResponse.json({
      resolved: [
        {
          compound_id: "c1",
          canonical_key: "inchikey:LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
          canonical_name: "ethanol",
          validation_status: "externally_validated",
        },
      ],
      failed: [
        {
          value: "NOTAKEY",
          reason:
            "not found in the database or PubChem. If it is a real compound, paste its SMILES (structure) instead.",
        },
      ],
    }),
  ),
  http.get(`${BASE}/analyses/r1`, () =>
    HttpResponse.json({
      analysis_id: "r1",
      analysis_name: null,
      disease_id: "d1",
      mode: "auto",
      status: "complete",
      current_stage: 1,
      stage_results: {
        "1": {
          count: 1,
          compounds: [{ compound_id: "c1", canonical_name: "Alpha" }],
          per_plant: {},
          state: "computed",
        },
      },
      created_at: null,
      completed_at: null,
      expires_at: null,
      error_message: null,
    }),
  ),
  http.get(`${BASE}/analyses/r2`, () => HttpResponse.json(ANALYSIS_WITH_STAGE2)),
  http.get(`${BASE}/analyses/r3`, () => HttpResponse.json(ANALYSIS_STAGE1_AWAITING)),
  http.get(`${BASE}/analyses/r4`, () => HttpResponse.json(ANALYSIS_STAGE1_AT_CAP)),
  // reset-from: echo back the same run with updated adme params
  http.post(`${BASE}/analyses/:id/reset-from/:stage`, () =>
    HttpResponse.json({ ...ANALYSIS_WITH_STAGE2, status: "stage_2_awaiting_approval" }),
  ),
  // stages edit: echo back the same run
  http.post(`${BASE}/analyses/:id/stages/:stage/edit`, () =>
    HttpResponse.json({ ...ANALYSIS_WITH_STAGE2 }),
  ),
);
