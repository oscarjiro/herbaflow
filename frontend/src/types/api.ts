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
  plant_aliases: string[]
}

export interface DiseaseResponse {
  disease_id: string
  disease_name: string
  ontology_id: string | null
  ontology_source: string | null
  disease_aliases: string[]
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
  // Only stop polling on genuinely terminal states:
  //   - 'complete' or 'failed' (top-level)
  //   - stage_N_rejected or stage_N_failed (stage-level errors)
  // All other states (pending, stage_N_running, stage_N_complete,
  // stage_N_awaiting_approval) are non-terminal — polling must continue.
  if (!s || typeof s !== 'string') return false
  return (
    s === 'complete' ||
    s === 'failed' ||
    /^stage_\d+_(rejected|failed)$/.test(s)
  )
}

export interface CreateAnalysisRequest {
  name: string
  mode: AnalysisMode
  plant_ids: string[]
  disease_id: string | null
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
  /** Set to true when user has added or removed compounds; drives stale banner */
  user_modified?: boolean
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
  /** Compound IDs that passed ADME screening */
  passed_compound_ids?: string[]
  /** Compound IDs admitted via the natural-product exception path */
  np_exception_compound_ids?: string[]
  /** All active compound IDs consumed by Stage 3 (passed + NP exceptions) */
  all_active_compound_ids?: string[]
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
  /** Set to true when user has added or removed targets; drives stale banner */
  user_modified?: boolean
}

// ============================================================================
// Pipeline Config Param Types (mirrors backend analysis/models.py)
// ============================================================================

export interface AdmeParamsConfig {
  max_mw: number
  max_logp: number
  max_hbd: number
  max_hba: number
  max_tpsa: number
  max_rotatable_bonds: number
  apply_veber: boolean
  apply_pains: boolean
  np_exception_threshold: number
  apply_adme_to_manual: boolean
}

export interface TargetParamsConfig {
  min_pchembl: number
  human_only: boolean
  min_assay_confidence: number
}

export interface DiseaseTargetParamsConfig {
  min_score: number
}

export interface PpiParamsConfig {
  min_confidence: number
  community_resolution?: number
}

export interface HubGeneParamsConfig {
  top_n: number
  use_hub_bottleneck: boolean
}

export interface EnrichmentParamsConfig {
  fdr_threshold: number
  sources: string[]
}

export interface ResetFromRequest {
  params?: Record<string, unknown>
  rerun?: boolean
}

export interface ApproveRequest {
  param_overrides?: Record<string, unknown>
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
  uniprot_accession: string | null
  score: number | null
  source: string
}

export interface Stage4Result {
  disease_id: string | null
  disease_name: string | null
  disease_target_count: number
  disease_gene_symbols?: string[]
  targets: DiseaseTargetResult[]
  /** Set to true when user has added or removed targets; drives stale banner */
  user_modified?: boolean
}

// Stage 5: Target Overlap
export interface OverlapStats {
  overlap: string[]
  overlap_count: number
  compound_only_count: number
  disease_only_count: number
  jaccard: number
  p_value: number | null
  significant: boolean
  venn?: {
    overlap: number
    disease_only: number
    compound_only: number
  }
}

export type Stage5Result = OverlapStats

// Stage 6: PPI Network (Cytoscape.js format)
export interface CytoscapeNodeData {
  id: string
  label: string
  type: 'hub' | 'overlap' | 'other'
  degree: number
  community_id?: number
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
  n_communities?: number
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
  community_id?: number
}

export interface CommunityHubGene {
  gene_symbol: string
  community_id: number
  community_degree: number
  community_betweenness: number
  community_closeness: number
  community_eigenvector: number
  community_size: number
}

export interface Stage7Result {
  ranked: HubGeneResult[]
  threshold_degree: number
  threshold_betweenness: number
  /** Per-community hub genes, keyed by community_id (stringified number from JSON). */
  community_hubs?: Record<string, CommunityHubGene[]>
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

export interface CommunityEnrichment {
  community_id: number
  gene_count: number
  genes: string[]
  go_bp: PathwayTerm[]
  go_mf: PathwayTerm[]
  go_cc: PathwayTerm[]
  kegg: PathwayTerm[]
}

export interface Stage8GlobalEnrichment {
  go_bp: PathwayTerm[]
  go_mf: PathwayTerm[]
  go_cc: PathwayTerm[]
  kegg: PathwayTerm[]
  hub_genes_queried: string[]
}

export interface Stage8Result {
  total_significant: number
  go_bp: PathwayTerm[]
  go_mf: PathwayTerm[]
  go_cc: PathwayTerm[]
  kegg: PathwayTerm[]
  hub_genes_queried: string[]
  communities?: CommunityEnrichment[]
  global_enrichment?: Stage8GlobalEnrichment
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

// ============================================================================
// Skipped Stage
// ============================================================================

export interface SkippedStageResult {
  status: 'skipped'
  input_mode: string
}

export function isSkippedStage(result: unknown): result is SkippedStageResult {
  return (
    typeof result === 'object' &&
    result !== null &&
    (result as SkippedStageResult).status === 'skipped'
  )
}

// T3.3: User-added targets
export interface AddUserTargetRequest {
  gene_symbol?: string
  uniprot_id?: string
}

export interface AddUserTargetResponse {
  target_id: string
  gene_symbol: string
  uniprot_id: string | null
  protein_name: string | null
}

export interface AddUserCompoundRequest {
  smiles?: string
  inchi?: string
}

export interface AddUserCompoundResponse {
  compound_id: string
  canonical_name: string
  smiles: string | null
}

// Manual compound input — inject SMILES/InChI strings as stage 1+2 results
export interface InjectCompoundsRequest {
  compounds: string[]
}

export interface InjectCompoundsResponse {
  injected: number
  failed: string[]
  duplicates_removed: number
  duplicate_names: string[]
  /** Compounds persisted to the DB cache (those resolved to a PubChem CID) */
  cached?: number
}

// Manual target input — inject gene symbols or UniProt accessions as stage 3 results
export interface InjectTargetsRequest {
  targets: string[]
  /** Lenient mode: skip UniProt validation and normalize gene symbols offline */
  skip_validation?: boolean
}

export interface InjectTargetsResponse {
  injected: number
  failed: string[]
  /** Inputs dropped due to deduplication */
  duplicates_removed?: number
  /** Labels for the dropped duplicate entries */
  duplicate_names?: string[]
  /** Targets persisted to the DB cache (validated, with a UniProt accession) */
  cached?: number
  /** HGNC alias/previous-symbol resolutions: [{ from, to }] */
  normalized?: Array<{ from: string; to: string }>
  /** Lenient inputs kept as-is (not found in HGNC / UniProt) */
  unrecognized?: string[]
}
