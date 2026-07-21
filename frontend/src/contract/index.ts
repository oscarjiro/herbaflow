import { z } from "zod";
import contract from "../../../shared/contracts/analysis.json";

export const MODES = contract.$defs.mode.enum as ["auto", "guided"];
export const MAX_PLANTS = contract.$defs.limits.properties.max_plants.const as number;
export const MAX_COMPOUNDS = contract.$defs.limits.properties.max_compounds.const as number;
export const MAX_TARGETS = contract.$defs.limits.properties.max_targets.const as number;
export const modeSchema = z.enum(MODES);
export const DEFAULT_MODE = contract.$defs.mode.default as (typeof MODES)[number];

// ---------------------------------------------------------------------------
// Input-mode vocabularies — derived from the shared contract.
// ---------------------------------------------------------------------------

export const PLANT_INPUT_MODES = contract.$defs.plant_input_mode.enum as [
  "selection",
  "manual_compounds",
  "manual_targets",
];
export const DISEASE_INPUT_MODES = contract.$defs.disease_input_mode.enum as [
  "selection",
  "manual_disease_targets",
];
export const plantInputModeSchema = z.enum(PLANT_INPUT_MODES);
export const diseaseInputModeSchema = z.enum(DISEASE_INPUT_MODES);
export const DEFAULT_PLANT_INPUT_MODE = contract.$defs.plant_input_mode
  .default as (typeof PLANT_INPUT_MODES)[number];
export const DEFAULT_DISEASE_INPUT_MODE = contract.$defs.disease_input_mode
  .default as (typeof DISEASE_INPUT_MODES)[number];

// ---------------------------------------------------------------------------
// ADME parameter metadata — derived from the shared contract.
// ---------------------------------------------------------------------------

type AdmeParamMeta = {
  default: number | boolean | string | string[];
  /** Hard lower bound (inclusive unless minExclusive is true). */
  min: number | undefined;
  /** True when the lower bound from the contract is exclusiveMinimum. */
  minExclusive: boolean;
  max: number | undefined;
  recommended_min: number | undefined;
  recommended_max: number | undefined;
  /** Allowed values for enum (select) params; undefined for free numeric/boolean params. */
  enum: (number | string)[] | undefined;
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
    enum: undefined,
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
    enum: undefined,
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
    enum: undefined,
    description: p.description as string,
  };
}

export const DISEASE_TARGETS_PARAMS = {
  min_score: diseaseTargetsEntry("min_score"),
} satisfies Record<string, AdmeParamMeta>;

export const DISEASE_TARGETS_NUMERIC_PARAMS = ["min_score"] as const;

// ---------------------------------------------------------------------------
// PPI (Stage 6 — STRING network) parameter metadata — derived from the contract.
//
// Both ppi params are enum-bounded (min_confidence numeric enum, network_type
// string enum) and render as <select>.
// ---------------------------------------------------------------------------

const ppiProps = contract.$defs.pipeline_parameters.properties.ppi.properties;

function ppiEntry(key: keyof typeof ppiProps): AdmeParamMeta {
  const p = ppiProps[key] as Record<string, unknown>;
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
  const enumVals = "enum" in p ? (p.enum as (number | string)[]) : undefined;
  return {
    default: p.default as number | boolean | string,
    min,
    minExclusive,
    max,
    recommended_min,
    recommended_max,
    enum: enumVals,
    description: p.description as string,
  };
}

export const PPI_PARAMS = {
  min_confidence: ppiEntry("min_confidence"),
  network_type: ppiEntry("network_type"),
} satisfies Record<string, AdmeParamMeta>;

export const PPI_NUMERIC_PARAMS = [] as const;
export const PPI_BOOLEAN_PARAMS = [] as const;
export const PPI_SELECT_PARAMS = ["min_confidence", "network_type"] as const;

// ---------------------------------------------------------------------------
// Hub-genes (Stage 7) parameter metadata — derived from the contract.
// ---------------------------------------------------------------------------

const hubGenesProps = contract.$defs.pipeline_parameters.properties.hub_genes.properties;

function hubGenesEntry(key: keyof typeof hubGenesProps): AdmeParamMeta {
  const p = hubGenesProps[key] as Record<string, unknown>;
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
    enum: undefined,
    description: p.description as string,
  };
}

export const HUB_GENES_PARAMS = {
  top_n: hubGenesEntry("top_n"),
} satisfies Record<string, AdmeParamMeta>;

export const HUB_GENES_NUMERIC_PARAMS = ["top_n"] as const;
export const HUB_GENES_BOOLEAN_PARAMS = [] as const;

// ---------------------------------------------------------------------------
// Enrichment (Stage 8) parameter metadata — derived from the contract.
//
// All Stage 8 parameters now surface through the shared ParamPanel, including
// `sources` as a checkbox-backed enum array.
// ---------------------------------------------------------------------------

const enrichmentProps = contract.$defs.pipeline_parameters.properties.enrichment.properties;

function enrichmentEntry(
  key: "significance_threshold" | "min_term_size" | "correction" | "sources" | "no_iea",
): AdmeParamMeta {
  const p = enrichmentProps[key] as Record<string, unknown>;
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
  const enumVals =
    "enum" in p
      ? (p.enum as (number | string)[])
      : "items" in p
        ? ((p.items as { enum?: (number | string)[] }).enum ?? undefined)
        : undefined;
  return {
    default: p.default as number | boolean | string | string[],
    min,
    minExclusive,
    max,
    recommended_min,
    recommended_max,
    enum: enumVals,
    description: p.description as string,
  };
}

export const ENRICHMENT_PARAMS = {
  significance_threshold: enrichmentEntry("significance_threshold"),
  min_term_size: enrichmentEntry("min_term_size"),
  correction: enrichmentEntry("correction"),
  sources: enrichmentEntry("sources"),
  no_iea: enrichmentEntry("no_iea"),
} satisfies Record<string, AdmeParamMeta>;

export const ENRICHMENT_NUMERIC_PARAMS = ["significance_threshold", "min_term_size"] as const;
export const ENRICHMENT_BOOLEAN_PARAMS = ["no_iea"] as const;
export const ENRICHMENT_SELECT_PARAMS = ["correction"] as const;
export const ENRICHMENT_ARRAY_PARAMS = ["sources"] as const;

// ---------------------------------------------------------------------------
// Per-stage data-source display names — one shared home in the contract.
// Each entry is {name, url} where url is null for pseudo-sources.
// ---------------------------------------------------------------------------

export type StageSourceEntry = { name: string; url: string | null };

const stageSourcesDefs = (
  contract.$defs as unknown as {
    stage_sources: {
      properties: {
        computed: { properties: Record<string, { default: StageSourceEntry[] }> };
        user_provided: { properties: Record<string, { default: StageSourceEntry[] }> };
      };
    };
  }
).stage_sources.properties;

function readStageSourceMap(group: {
  properties: Record<string, { default: StageSourceEntry[] }>;
}): Record<number, StageSourceEntry[]> {
  const out: Record<number, StageSourceEntry[]> = {};
  for (const [k, v] of Object.entries(group.properties)) out[Number(k)] = v.default;
  return out;
}

export const STAGE_SOURCES = readStageSourceMap(stageSourcesDefs.computed);
export const USER_PROVIDED_SOURCES = readStageSourceMap(stageSourcesDefs.user_provided);
