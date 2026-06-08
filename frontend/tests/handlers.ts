import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

const BASE = "http://localhost:8000";

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
);
