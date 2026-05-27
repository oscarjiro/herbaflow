/**
 * Zod validation schemas for the analysis setup form.
 *
 * These mirror the Pydantic constraints in backend/app/schemas/analysis.py
 * so that invalid payloads are rejected on both sides.
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** Analysis run mode (guided = step-by-step approval, auto = fully automated). */
export const analysisModeSchema = z.enum(['guided', 'auto'])

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
  np_exception_threshold: z.number().min(0, 'Must be ≥ 0').max(1, 'Must be ≤ 1'),

  // Targets (Stage 3)
  min_pchembl: z.number().min(0, 'Must be ≥ 0').max(15, 'Must be ≤ 15'),
  human_only: z.boolean(),
  min_assay_confidence: z.number().int().min(0, 'Must be 0–9').max(9, 'Must be 0–9'),

  // Disease Targets (Stage 4)
  min_score: z.number().min(0, 'Must be ≥ 0').max(1, 'Must be ≤ 1'),

  // Network (Stage 6)
  min_confidence: z.number().min(0, 'Must be ≥ 0').max(1, 'Must be ≤ 1'),

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

/** Require disease_ids when diseaseInputMode is 'disease'; allow empty for 'manual_targets'. */
function diseaseIdsField(diseaseInputMode: 'disease' | 'manual_targets') {
  return diseaseInputMode === 'manual_targets'
    ? z.array(z.string())
    : z.array(z.string()).min(1, 'Select at least one disease')
}

/** Require disease_targets when diseaseInputMode is 'manual_targets'. */
function diseaseTargetsField(diseaseInputMode: 'disease' | 'manual_targets') {
  return diseaseInputMode === 'manual_targets'
    ? z.array(z.string().min(1)).min(1, 'Enter at least one disease target').max(200, 'Maximum 200 targets')
    : z.array(z.string()).optional()
}

// ---------------------------------------------------------------------------
// Setup form — standard mode
// ---------------------------------------------------------------------------

export function makeSetupFormStandardSchema(diseaseInputMode: 'disease' | 'manual_targets' = 'disease') {
  return z.object({
    mode: analysisModeSchema,
    plant_ids: z.array(z.string()).min(1, 'Select at least one plant'),
    disease_ids: diseaseIdsField(diseaseInputMode),
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
    disease_ids: diseaseIdsField(diseaseInputMode),
    disease_targets: diseaseTargetsField(diseaseInputMode),
    compounds: z
      .array(z.string().min(1))
      .min(1, 'Enter at least one compound')
      .max(100, 'Maximum 100 compounds'),
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
    disease_ids: diseaseIdsField(diseaseInputMode),
    disease_targets: diseaseTargetsField(diseaseInputMode),
    targets: z
      .array(z.string().min(1))
      .min(1, 'Enter at least one target')
      .max(200, 'Maximum 200 targets'),
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
    .max(100, 'Maximum 100 compounds allowed'),
})

export const injectTargetsSchema = z.object({
  targets: z
    .array(z.string().min(1))
    .min(1, 'At least one target is required')
    .max(200, 'Maximum 200 targets allowed'),
})

// ---------------------------------------------------------------------------

/**
 * Validate the setup form data for any input mode.
 * Returns { success, errors } where errors is a flat map of field → message.
 */
export type SetupFormErrors = Partial<{
  mode: string
  plant_ids: string
  disease_ids: string
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
