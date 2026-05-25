/**
 * API Type Definitions
 *
 * TypeScript interfaces matching FastAPI backend schemas exactly.
 * Field names use snake_case to match backend responses.
 */

// ============================================================================
// Basic Resource Types
// ============================================================================

export interface PlantResponse {
  plant_id: string
  canonical_scientific_name: string
  family_name: string | null
  compound_count: number
}

export interface DiseaseResponse {
  disease_id: string
  disease_name: string
  ontology_id: string | null
  ontology_source: string | null
}

export interface CompoundResponse {
  compound_id: string
  canonical_name: string
  smiles: string | null
  chembl_id: string | null
  pubchem_cid: string | null
  molecular_weight: number | null
  logp: number | null
  tpsa: number | null
  hbond_donors: number | null
  hbond_acceptors: number | null
  rotatable_bonds: number | null
  np_likeness_score: number | null
  num_ro5_violations: number | null
  lipinski_source: string | null
}

// ============================================================================
// Analysis Types
// ============================================================================

export type AnalysisMode = 'guided' | 'auto'

export type AnalysisStatus =
  | 'pending'
  | 'stage_1_running'
  | 'stage_1_complete'
  | 'stage_1_failed'
  | 'stage_1_rejected'
  | 'stage_1_awaiting_approval'
  | 'stage_2_running'
  | 'stage_2_complete'
  | 'stage_2_failed'
  | 'stage_2_rejected'
  | 'stage_2_awaiting_approval'
  | 'stage_3_running'
  | 'stage_3_complete'
  | 'stage_3_failed'
  | 'stage_3_rejected'
  | 'stage_3_awaiting_approval'
  | 'stage_4_running'
  | 'stage_4_complete'
  | 'stage_4_failed'
  | 'stage_4_rejected'
  | 'stage_4_awaiting_approval'
  | 'stage_5_running'
  | 'stage_5_complete'
  | 'stage_5_failed'
  | 'stage_5_rejected'
  | 'stage_5_awaiting_approval'
  | 'stage_6_running'
  | 'stage_6_complete'
  | 'stage_6_failed'
  | 'stage_6_rejected'
  | 'stage_6_awaiting_approval'
  | 'stage_7_running'
  | 'stage_7_complete'
  | 'stage_7_failed'
  | 'stage_7_rejected'
  | 'stage_7_awaiting_approval'
  | 'stage_8_running'
  | 'stage_8_complete'
  | 'stage_8_failed'
  | 'stage_8_rejected'
  | 'stage_8_awaiting_approval'
  | 'complete'
  | 'failed'
  | (string & {})

export function isTerminalStatus(s: string): boolean {
  return /complete$|failed$|rejected$/.test(s)
}

export interface CreateAnalysisRequest {
  name: string
  mode: AnalysisMode
  plant_ids: string[]
  disease_ids: string[]
  parameters: Record<string, unknown>
}

export interface AnalysisStatusResponse {
  analysis_id: string // UUID as string in JSON
  status: AnalysisStatus
  mode: AnalysisMode
  current_stage: number | null
  progress: Record<string, number>
  created_at: string | null // ISO 8601 datetime string
  updated_at: string | null
  error_message: string | null
  expires_at: string | null // ISO 8601 datetime; set when status = 'complete'
}

export interface AnalysisRunResponse {
  analysis_id: string // UUID as string in JSON
  analysis_name: string
  status: AnalysisStatus
  mode: AnalysisMode
  disease_id: string | null
  current_stage: number | null
  stage_results: Record<string, unknown>
  parameters: Record<string, unknown> | null
  created_at: string | null // ISO 8601 datetime string
  completed_at: string | null
  expires_at: string | null // set on completion; null until complete
  error_message: string | null
}

// ============================================================================
// Stage Result Types
// ============================================================================

// Stage 1: Compound Selection
export interface CompoundResult {
  compound_id: string
  canonical_name: string
  plant_ids: string[]
}

export interface Stage1Result {
  total_compounds: number
  plants_covered: number
  compounds: CompoundResult[]
}

// Stage 2: ADME Screening
export interface AdmeCompoundResult extends CompoundResult {
  adme_pass: boolean
  is_np_exception: boolean
  molecular_weight: number | null
  logp: number | null
  tpsa: number | null
  hbond_donors: number | null
  hbond_acceptors: number | null
  np_likeness_score: number | null
  rotatable_bonds: number | null
  is_pains_positive: boolean
}

export interface Stage2Result {
  passed: number
  failed: number
  np_exceptions: number
  compounds: AdmeCompoundResult[]
}

// Stage 3: Target Identification
export interface TargetResult {
  gene_symbol: string
  uniprot_id: string
  compound_count: number
  compound_ids: string[]
  /** Source that identified this target: "chembl" (primary) or "pubchem_bioassay" (fallback) */
  source: 'chembl' | 'pubchem_bioassay' | 'user_provided'
}

export interface UncoveredCompound {
  compound_id: string
  canonical_name: string
  smiles: string | null
}

export interface Stage3Result {
  target_count: number
  /** Backend field name: coverage_pct (renamed from coverage_percent in stage3 output) */
  coverage_pct: number
  targets: TargetResult[]
  /** Per-compound source tracking: compound_id → list of sources that found targets for it */
  compound_sources: Record<string, Array<'chembl' | 'pubchem_bioassay' | 'user_provided'>>
  /** Compounds with zero targets after ChEMBL + PubChem; used for STP Coverage section */
  uncovered_compounds: UncoveredCompound[]
}

// Stage 3: STP Import
export interface STPTargetImport {
  uniprot_id: string
  gene_symbol: string
  probability: number
}

export interface ImportTargetsRequest {
  compound_id: string
  targets: STPTargetImport[]
}

export interface ImportTargetsResponse {
  imported: number
  skipped: number
}

// Stage 4: Disease Targets
export interface DiseaseTargetResult {
  gene_symbol: string
  uniprot_id: string
  association_score: number | null
  disease_name: string
  source: string
}

export interface Stage4Result {
  disease_target_count: number
  targets: DiseaseTargetResult[]
}

// Stage 5: Target Overlap
export interface Stage5Result {
  compound_only_count: number
  overlap_count: number
  disease_only_count: number
  /** Backend field name: jaccard (not jaccard_index) */
  jaccard: number
  p_value: number | null
  significant: boolean
  /** Backend field name: overlap (not overlap_genes) */
  overlap: string[]
  venn?: {
    overlap: number
    disease_only: number
    compound_only: number
  }
}

// Stage 6: PPI Network (Cytoscape.js format)
export interface CytoscapeNodeData {
  id: string
  label: string
  type: 'hub' | 'overlap' | 'other'
  degree: number
}

export interface CytoscapeNode {
  data: CytoscapeNodeData
}

export interface CytoscapeEdgeData {
  id?: string          // Cytoscape auto-generates if omitted
  source: string
  target: string
  weight: number       // combined_score stored as weight for Cytoscape mapData
  combined_score?: number
}

export interface CytoscapeEdge {
  data: CytoscapeEdgeData
}

export interface Stage6Result {
  node_count: number
  edge_count: number
  nodes: CytoscapeNode[]
  edges: CytoscapeEdge[]
  min_confidence: number
}

// Stage 7: Hub Gene Analysis
export interface HubGeneResult {
  rank: number
  gene_symbol: string
  degree: number
  betweenness: number
  closeness: number
  eigenvector: number
  is_hub: boolean
  is_hub_bottleneck: boolean
}

export interface Stage7Result {
  ranked: HubGeneResult[]
  threshold_degree: number
  threshold_betweenness: number
}

// Stage 8: Pathway Enrichment
export type PathwaySource = 'GO:BP' | 'GO:MF' | 'GO:CC' | 'KEGG'

export interface PathwayTerm {
  term_id: string
  term_name: string
  p_value: number
  fdr: number
  intersection_size: number
  term_size: number
  genes: string[]
}

export interface Stage8Result {
  total_significant: number
  go_bp: PathwayTerm[]
  go_mf: PathwayTerm[]
  go_cc: PathwayTerm[]
  kegg: PathwayTerm[]
  hub_genes_queried: string[]
}

// ============================================================================
// Union Type for All Stage Results
// ============================================================================

export type StageResult =
  | Stage1Result
  | Stage2Result
  | Stage3Result
  | Stage4Result
  | Stage5Result
  | Stage6Result
  | Stage7Result
  | Stage8Result
