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

/** A non-empty string trimmed to max 200 chars (analysis name). */
export const analysisNameSchema = z
  .string()
  .min(1, 'Analysis name is required')
  .max(200, 'Analysis name must be 200 characters or fewer')
  .transform((v) => v.trim())
  .refine((v) => v.length > 0, 'Analysis name cannot be blank')

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
// Setup form — standard mode
// ---------------------------------------------------------------------------

export const setupFormStandardSchema = z.object({
  name: analysisNameSchema,
  mode: analysisModeSchema,
  plant_ids: z.array(z.string()).min(1, 'Select at least one plant'),
  disease_ids: z.array(z.string()).min(1, 'Select at least one disease'),
  parameters: advancedParamsSchema,
})

// ---------------------------------------------------------------------------
// Setup form — manual_compounds mode
// ---------------------------------------------------------------------------

export const setupFormManualCompoundsSchema = z.object({
  name: analysisNameSchema,
  mode: analysisModeSchema,
  disease_ids: z.array(z.string()).min(1, 'Select at least one disease'),
  compounds: z
    .array(z.string().min(1))
    .min(1, 'Enter at least one compound')
    .max(100, 'Maximum 100 compounds'),
  parameters: advancedParamsSchema,
})

// ---------------------------------------------------------------------------
// Setup form — manual_targets mode
// ---------------------------------------------------------------------------

export const setupFormManualTargetsSchema = z.object({
  name: analysisNameSchema,
  mode: analysisModeSchema,
  disease_ids: z.array(z.string()).min(1, 'Select at least one disease'),
  targets: z
    .array(z.string().min(1))
    .min(1, 'Enter at least one target')
    .max(200, 'Maximum 200 targets'),
  parameters: advancedParamsSchema,
})

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
// Discriminated union for the full setup form
// ---------------------------------------------------------------------------

/**
 * Validate the setup form data for any input mode.
 * Returns { success, errors } where errors is a flat map of field → message.
 */
export type SetupFormErrors = Partial<{
  name: string
  mode: string
  plant_ids: string
  disease_ids: string
  compounds: string
  targets: string
  parameters: string
}>

export function validateSetupForm(
  inputMode: 'standard' | 'manual_compounds' | 'manual_targets',
  data: Record<string, unknown>,
): { success: boolean; errors: SetupFormErrors } {
  const schema =
    inputMode === 'manual_compounds'
      ? setupFormManualCompoundsSchema
      : inputMode === 'manual_targets'
        ? setupFormManualTargetsSchema
        : setupFormStandardSchema

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
