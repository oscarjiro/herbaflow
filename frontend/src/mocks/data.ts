// Fixture data matching the backend API schemas.
// Inline types used here since @/types/api does not exist yet (Task 5).

interface PlantFixture {
  id: string
  scientific_name: string
  common_names: string[]
  family: string
  compound_count: number
}

interface DiseaseFixture {
  id: string
  name: string
  ontology_id: string
  source: string
}

export const plantsFixture: PlantFixture[] = [
  {
    id: 'pl_knapsack_C00001234',
    scientific_name: 'Andrographis paniculata',
    common_names: ['King of Bitters', 'Kalmegh'],
    family: 'Acanthaceae',
    compound_count: 42,
  },
  {
    id: 'pl_knapsack_C00005678',
    scientific_name: 'Curcuma longa',
    common_names: ['Turmeric'],
    family: 'Zingiberaceae',
    compound_count: 87,
  },
]

export const diseasesFixture: DiseaseFixture[] = [
  {
    id: 'dtg_mondo_0005148',
    name: 'type 2 diabetes mellitus',
    ontology_id: 'MONDO:0005148',
    source: 'mondo',
  },
  {
    id: 'dtg_mondo_0004981',
    name: 'atrial fibrillation',
    ontology_id: 'MONDO:0004981',
    source: 'mondo',
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
