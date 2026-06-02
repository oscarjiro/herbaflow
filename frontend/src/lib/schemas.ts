/**
 * Zod validation schemas for the analysis setup form.
 *
 * These mirror the Pydantic constraints in backend/app/schemas/analysis.py
 * so that invalid payloads are rejected on both sides.
 */
import { z } from 'zod'
import analysisContract from '@shared/contracts/analysis.json'

// ---------------------------------------------------------------------------
// Input size limits — mirrors backend HARD_CAP_* / SOFT_CAP_* constants
// Based on published network pharmacology study scales:
//   Plants:    90%+ of NP studies ≤ 20 herbs; Indonesian jamu formulas 3–15 plants.
//              Li S et al. (2014) Evid Based Complement Alternat Med;
//              Jiang Y et al. (2021) systematic review of TCM-NP studies.
//   Compounds: 20 plants × ~250 KNApSAcK compounds/plant ≈ 5,000 pre-ADME ceiling.
//              Zhou Y et al. (2019) Evid Based Complement Alternat Med.
//   Targets (compound-side): covers entire human druggable proteome (~4,719 proteins).
//              Finan C et al. (2017) Sci Transl Med. Targets overlap with disease
//              targets at Stage 5; STRING-DB receives the intersection only.
//              Szklarczyk D et al. (2023) STRING v12; Traag VA et al. (2019) Sci Rep.
//   Targets (disease-side): Open Targets single-disease associations 200–2,000.
//              Ochoa et al. (2021) Nucleic Acids Res; Piñero et al. (2020) Nucleic Acids Res.
// ---------------------------------------------------------------------------

// Hard caps enforced by backend Pydantic validation (max_length); requests exceeding these return HTTP 422.
export const HARD_CAP_PLANTS = 20
export const HARD_CAP_MANUAL_COMPOUNDS = 5000
export const HARD_CAP_MANUAL_TARGETS = 5000
export const HARD_CAP_DISEASE_TARGETS = 2000
// Soft caps: planned for UI warnings (yellow highlight when approaching the hard cap).
export const SOFT_CAP_PLANTS = 10
export const SOFT_CAP_MANUAL_COMPOUNDS = 1000
export const SOFT_CAP_MANUAL_TARGETS = 500
export const SOFT_CAP_DISEASE_TARGETS = 500

// ---------------------------------------------------------------------------
// Format validators — UniProt accession, HGNC gene symbol, SMILES
// ---------------------------------------------------------------------------

/**
 * UniProt accession: HUPO-PSI standard two-pattern format.
 *   6-char legacy:  [OPQ][0-9][A-Z0-9]{3}[0-9]
 *   10-char new:    [A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}
 * Mirrors UNIPROT_ACCESSION_RE in backend/app/schemas/analysis.py.
 */
export const UNIPROT_RE =
  /^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$/

export const uniprotAccessionSchema = z
  .string()
  .regex(UNIPROT_RE, 'Invalid UniProt accession format (e.g., P04637 or Q9Y6I3)')

/**
 * HGNC gene symbol: uppercase letter start, 1–25 chars, A-Z / 0-9 / hyphen only.
 * Mirrors GENE_SYMBOL_RE in backend/app/schemas/analysis.py.
 */
export const geneSymbolSchema = z
  .string()
  .regex(
    /^[A-Z][A-Z0-9\-]{0,24}$/,
    'Gene symbol must be uppercase and follow HGNC format (e.g., TP53 or HIF-1A)',
  )

/**
 * SMILES minimum validation: length >= 3, printable ASCII only.
 * Chemical correctness is delegated to PubChem — we only block obviously malformed input.
 * Mirrors validate_smiles_minimum in backend/app/schemas/analysis.py.
 */
export const smilesSchema = z
  .string()
  .min(3, 'SMILES string is too short; minimum length is 3')
  .refine(
    (v) => /^[\x20-\x7E]+$/.test(v),
    'SMILES must contain only printable ASCII characters',
  )

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** Analysis run mode (guided = step-by-step approval, auto = fully automated). */
export const analysisModeSchema = z.enum(
  analysisContract.analysis_mode as [string, ...string[]],
)

/** Input mode for the setup form. */
export const inputModeSchema = z.enum(['standard', 'manual_compounds', 'manual_targets'])

// ---------------------------------------------------------------------------
// Advanced parameters
// ---------------------------------------------------------------------------

export const advancedParamsSchema = z.object({
  // ADME (Stage 2)
  max_mw: z.number().min(0, 'Must be ≥ 0').max(2000, 'Must be ≤ 2000'),
  max_logp: z.number().min(-10, 'Must be ≥ -10').max(20, 'Must be ≤ 20'),
  max_hbd: z.number().int().min(0, 'Must be ≥ 0').max(20, 'Must be ≤ 20'),
  max_hba: z.number().int().min(0, 'Must be ≥ 0').max(30, 'Must be ≤ 30'),
  max_tpsa: z.number().min(0, 'Must be ≥ 0').max(500, 'Must be ≤ 500'),
  max_rotatable_bonds: z.number().int().min(0, 'Must be ≥ 0').max(50, 'Must be ≤ 50'),
  apply_veber: z.boolean(),
  apply_pains: z.boolean(),
  np_exception_threshold: z.number().min(0, 'Must be ≥ 0').max(1, 'Must be ≤ 1'),
  apply_adme_to_manual: z.boolean(),

  // Targets (Stage 3)
  min_pchembl: z.number().min(0, 'Must be ≥ 0').max(14, 'Must be ≤ 14'),
  human_only: z.boolean(),
  min_assay_confidence: z.number().int().min(0, 'Must be 0–9').max(9, 'Must be 0–9'),

  // Disease Targets (Stage 4)
  min_score: z.number().min(0, 'Must be ≥ 0').max(1, 'Must be ≤ 1'),

  // Network (Stage 6) — STRING-DB standard confidence presets only
  // (Low=0.15, Medium=0.40, High=0.70, Very High=0.90)
  min_confidence: z.union([
    z.literal(0.15),
    z.literal(0.4),
    z.literal(0.7),
    z.literal(0.9),
  ]),

  // Hub Genes (Stage 7)
  top_n: z.number().int().min(1, 'Must be ≥ 1').max(200, 'Must be ≤ 200'),
  use_hub_bottleneck: z.boolean(),

  // Enrichment (Stage 8)
  fdr_threshold: z.number().gt(0, 'Must be > 0').max(1, 'Must be ≤ 1'),
  sources: z.array(z.string()).min(1, 'At least one pathway source required'),
})

export type AdvancedParamsInput = z.input<typeof advancedParamsSchema>
export type AdvancedParamsOutput = z.output<typeof advancedParamsSchema>

// ---------------------------------------------------------------------------
// Disease ID field — conditionally required based on disease input mode
// ---------------------------------------------------------------------------

/** Require disease_id when diseaseInputMode is 'disease'; allow absent for 'manual_targets'. */
function diseaseIdField(diseaseInputMode: 'disease' | 'manual_targets') {
  return diseaseInputMode === 'manual_targets'
    ? z.string().nullish()
    : z.string().min(1, 'Select a disease')
}

/** Require disease_targets when diseaseInputMode is 'manual_targets'. */
function diseaseTargetsField(diseaseInputMode: 'disease' | 'manual_targets') {
  return diseaseInputMode === 'manual_targets'
    ? z.array(z.string().min(1)).min(1, 'Enter at least one disease target').max(HARD_CAP_DISEASE_TARGETS, `Maximum ${HARD_CAP_DISEASE_TARGETS} targets`)
    : z.array(z.string()).optional()
}

// ---------------------------------------------------------------------------
// Setup form — standard mode
// ---------------------------------------------------------------------------

export function makeSetupFormStandardSchema(diseaseInputMode: 'disease' | 'manual_targets' = 'disease') {
  return z.object({
    mode: analysisModeSchema,
    plant_ids: z
      .array(z.string())
      .min(1, 'Select at least one plant')
      .max(HARD_CAP_PLANTS, `Maximum ${HARD_CAP_PLANTS} plants per analysis`),
    disease_id: diseaseIdField(diseaseInputMode),
    disease_targets: diseaseTargetsField(diseaseInputMode),
    parameters: advancedParamsSchema,
  })
}

/** @deprecated use makeSetupFormStandardSchema() */
export const setupFormStandardSchema = makeSetupFormStandardSchema('disease')

// ---------------------------------------------------------------------------
// Setup form — manual_compounds mode
// ---------------------------------------------------------------------------

export function makeSetupFormManualCompoundsSchema(diseaseInputMode: 'disease' | 'manual_targets' = 'disease') {
  return z.object({
    mode: analysisModeSchema,
    disease_id: diseaseIdField(diseaseInputMode),
    disease_targets: diseaseTargetsField(diseaseInputMode),
    compounds: z
      .array(z.string().min(1))
      .min(1, 'Enter at least one compound')
      .max(HARD_CAP_MANUAL_COMPOUNDS, `Maximum ${HARD_CAP_MANUAL_COMPOUNDS} compounds per analysis`),
    parameters: advancedParamsSchema,
  })
}

/** @deprecated use makeSetupFormManualCompoundsSchema() */
export const setupFormManualCompoundsSchema = makeSetupFormManualCompoundsSchema('disease')

// ---------------------------------------------------------------------------
// Setup form — manual_targets mode (compound targets)
// ---------------------------------------------------------------------------

export function makeSetupFormManualTargetsSchema(diseaseInputMode: 'disease' | 'manual_targets' = 'disease') {
  return z.object({
    mode: analysisModeSchema,
    disease_id: diseaseIdField(diseaseInputMode),
    disease_targets: diseaseTargetsField(diseaseInputMode),
    targets: z
      .array(z.string().min(1))
      .min(1, 'Enter at least one target')
      .max(HARD_CAP_MANUAL_TARGETS, `Maximum ${HARD_CAP_MANUAL_TARGETS} targets per analysis`),
    parameters: advancedParamsSchema,
  })
}

/** @deprecated use makeSetupFormManualTargetsSchema() */
export const setupFormManualTargetsSchema = makeSetupFormManualTargetsSchema('disease')

// ---------------------------------------------------------------------------
// Inject requests (mirrors Pydantic InjectCompoundsRequest / InjectTargetsRequest)
// ---------------------------------------------------------------------------

export const injectCompoundsSchema = z.object({
  compounds: z
    .array(z.string().min(1))
    .min(1, 'At least one compound is required')
    .max(HARD_CAP_MANUAL_COMPOUNDS, `Maximum ${HARD_CAP_MANUAL_COMPOUNDS} compounds allowed`),
})

export const injectTargetsSchema = z.object({
  targets: z
    .array(z.string().min(1))
    .min(1, 'At least one target is required')
    .max(HARD_CAP_MANUAL_TARGETS, `Maximum ${HARD_CAP_MANUAL_TARGETS} targets allowed`),
})

// ---------------------------------------------------------------------------

/**
 * Validate the setup form data for any input mode.
 * Returns { success, errors } where errors is a flat map of field → message.
 */
export type SetupFormErrors = Partial<{
  mode: string
  plant_ids: string
  disease_id: string
  disease_targets: string
  compounds: string
  targets: string
  parameters: string
}>

export function validateSetupForm(
  inputMode: 'standard' | 'manual_compounds' | 'manual_targets',
  diseaseInputMode: 'disease' | 'manual_targets',
  data: Record<string, unknown>,
): { success: boolean; errors: SetupFormErrors } {
  const schema =
    inputMode === 'manual_compounds'
      ? makeSetupFormManualCompoundsSchema(diseaseInputMode)
      : inputMode === 'manual_targets'
        ? makeSetupFormManualTargetsSchema(diseaseInputMode)
        : makeSetupFormStandardSchema(diseaseInputMode)

  const result = schema.safeParse(data)
  if (result.success) return { success: true, errors: {} }

  const errors: SetupFormErrors = {}
  for (const issue of result.error.issues) {
    const field = issue.path[0] as keyof SetupFormErrors | undefined
    if (field && !errors[field]) {
      errors[field] = issue.message
    }
  }
  return { success: false, errors }
}
