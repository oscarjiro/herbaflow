import { z } from "zod";
import contract from "../../../shared/contracts/analysis.json";

export const MODES = contract.$defs.mode.enum as ["auto", "guided"];
export const MAX_PLANTS = contract.$defs.limits.properties.max_plants.const as number;
export const MAX_COMPOUNDS = contract.$defs.limits.properties.max_compounds.const as number;
export const MAX_TARGETS = contract.$defs.limits.properties.max_targets.const as number;
export const modeSchema = z.enum(MODES);
export const DEFAULT_MODE = contract.$defs.mode.default as (typeof MODES)[number];

// ---------------------------------------------------------------------------
// ADME parameter metadata — derived from the shared contract.
// ---------------------------------------------------------------------------

type AdmeParamMeta = {
  default: number | boolean;
  /** Hard lower bound (inclusive unless minExclusive is true). */
  min: number | undefined;
  /** True when the lower bound from the contract is exclusiveMinimum. */
  minExclusive: boolean;
  max: number | undefined;
  recommended_min: number | undefined;
  recommended_max: number | undefined;
  description: string;
};

const admeProps = contract.$defs.pipeline_parameters.properties.adme.properties;

function admeEntry(key: keyof typeof admeProps): AdmeParamMeta {
  const p = admeProps[key] as Record<string, unknown>;
  const minExclusive = "exclusiveMinimum" in p && !("minimum" in p);
  const min =
    "minimum" in p
      ? (p.minimum as number)
      : "exclusiveMinimum" in p
        ? (p.exclusiveMinimum as number)
        : undefined;
  const max = "maximum" in p ? (p.maximum as number) : undefined;
  const recommended_min = "recommended_min" in p ? (p.recommended_min as number) : undefined;
  const recommended_max = "recommended_max" in p ? (p.recommended_max as number) : undefined;
  return {
    default: p.default as number | boolean,
    min,
    minExclusive,
    max,
    recommended_min,
    recommended_max,
    description: p.description as string,
  };
}

export const ADME_PARAMS = {
  max_mw: admeEntry("max_mw"),
  max_logp: admeEntry("max_logp"),
  max_hbd: admeEntry("max_hbd"),
  max_hba: admeEntry("max_hba"),
  max_tpsa: admeEntry("max_tpsa"),
  max_rotatable_bonds: admeEntry("max_rotatable_bonds"),
  apply_veber: admeEntry("apply_veber"),
  np_exception_threshold: admeEntry("np_exception_threshold"),
  apply_np_exception: admeEntry("apply_np_exception"),
  max_violations: admeEntry("max_violations"),
  skip_adme: admeEntry("skip_adme"),
} satisfies Record<string, AdmeParamMeta>;

// Stable ordered lists for panel rendering.
export const ADME_NUMERIC_PARAMS = [
  "max_mw",
  "max_logp",
  "max_hbd",
  "max_hba",
  "max_tpsa",
  "max_rotatable_bonds",
  "np_exception_threshold",
  "max_violations",
] as const;

export const ADME_BOOLEAN_PARAMS = ["apply_veber", "apply_np_exception", "skip_adme"] as const;

// ---------------------------------------------------------------------------
// Target parameter metadata — derived from the shared contract.
// ---------------------------------------------------------------------------

const targetProps = contract.$defs.pipeline_parameters.properties.target.properties;

function targetEntry(key: keyof typeof targetProps): AdmeParamMeta {
  const p = targetProps[key] as Record<string, unknown>;
  const minExclusive = "exclusiveMinimum" in p && !("minimum" in p);
  const min =
    "minimum" in p
      ? (p.minimum as number)
      : "exclusiveMinimum" in p
        ? (p.exclusiveMinimum as number)
        : undefined;
  const max = "maximum" in p ? (p.maximum as number) : undefined;
  const recommended_min = "recommended_min" in p ? (p.recommended_min as number) : undefined;
  const recommended_max = "recommended_max" in p ? (p.recommended_max as number) : undefined;
  return {
    default: p.default as number | boolean,
    min,
    minExclusive,
    max,
    recommended_min,
    recommended_max,
    description: p.description as string,
  };
}

export const TARGET_PARAMS = {
  min_pchembl: targetEntry("min_pchembl"),
  min_assay_confidence: targetEntry("min_assay_confidence"),
} satisfies Record<string, AdmeParamMeta>;

export const TARGET_NUMERIC_PARAMS = ["min_pchembl", "min_assay_confidence"] as const;

// ---------------------------------------------------------------------------
// Disease-target parameter metadata — derived from the shared contract.
// ---------------------------------------------------------------------------

const diseaseTargetsProps =
  contract.$defs.pipeline_parameters.properties.disease_targets.properties;

function diseaseTargetsEntry(key: keyof typeof diseaseTargetsProps): AdmeParamMeta {
  const p = diseaseTargetsProps[key] as Record<string, unknown>;
  const minExclusive = "exclusiveMinimum" in p && !("minimum" in p);
  const min =
    "minimum" in p
      ? (p.minimum as number)
      : "exclusiveMinimum" in p
        ? (p.exclusiveMinimum as number)
        : undefined;
  const max = "maximum" in p ? (p.maximum as number) : undefined;
  const recommended_min = "recommended_min" in p ? (p.recommended_min as number) : undefined;
  const recommended_max = "recommended_max" in p ? (p.recommended_max as number) : undefined;
  return {
    default: p.default as number | boolean,
    min,
    minExclusive,
    max,
    recommended_min,
    recommended_max,
    description: p.description as string,
  };
}

export const DISEASE_TARGETS_PARAMS = {
  min_score: diseaseTargetsEntry("min_score"),
} satisfies Record<string, AdmeParamMeta>;

export const DISEASE_TARGETS_NUMERIC_PARAMS = ["min_score"] as const;
