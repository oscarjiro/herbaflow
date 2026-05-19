// Fixture data matching the backend API schemas exactly.
import type { PlantResponse, DiseaseResponse } from '@/types/api'

export const plantsFixture: PlantResponse[] = [
  {
    plant_id: 'pl_knapsack_C00001234',
    canonical_scientific_name: 'Andrographis paniculata',
    family_name: 'Acanthaceae',
    compound_count: 42,
  },
  {
    plant_id: 'pl_knapsack_C00005678',
    canonical_scientific_name: 'Curcuma longa',
    family_name: 'Zingiberaceae',
    compound_count: 87,
  },
]

export const diseasesFixture: DiseaseResponse[] = [
  {
    disease_id: 'dtg_mondo_0005148',
    disease_name: 'type 2 diabetes mellitus',
    ontology_id: 'MONDO:0005148',
    ontology_source: 'mondo',
  },
  {
    disease_id: 'dtg_mondo_0004981',
    disease_name: 'atrial fibrillation',
    ontology_id: 'MONDO:0004981',
    ontology_source: 'mondo',
  },
]

export const analysisFixture = {
  analysis_id: 'test-id-1',
  analysis_name: 'Andrographis × T2D — 2026-05-19',
  mode: 'guided',
  status: 'stage_3_awaiting_approval',
  current_stage: 3,
  created_at: '2026-05-19T10:00:00Z',
  updated_at: '2026-05-19T10:05:00Z',
  plant_ids: ['pl_knapsack_C00001234'],
  disease_id: 'dtg_mondo_0005148',
  parameters: {},
  stage_results: {
    '1': {
      total_compounds: 42,
      plants_covered: 1,
      compounds: [],
    },
    '2': {
      passed: 30,
      failed: 12,
      np_exceptions: 3,
      compounds: [],
    },
    '3': {
      target_count: 18,
      coverage_percent: 85.7,
      targets: [],
    },
    '4': null,
    '5': null,
    '6': null,
    '7': null,
    '8': null,
  },
  error_message: null,
}

export const statusFixture = {
  analysis_id: 'test-id-1',
  status: 'stage_3_awaiting_approval',
  current_stage: 3,
  stage_statuses: {
    '1': 'complete',
    '2': 'complete',
    '3': 'awaiting_approval',
    '4': 'pending',
    '5': 'pending',
    '6': 'pending',
    '7': 'pending',
    '8': 'pending',
  },
  error_message: null,
  elapsed_seconds: 45.2,
}
