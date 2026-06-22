import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { listDiseases, listPlants, createAnalysis } from "../api/sdk.gen";
import type { Problem } from "../lib/problem";
import { notifyError } from "../lib/toast";
import type { AnalysisRead, ResolvedCompound, ResolvedTarget } from "../api/types.gen";
import { mergeById } from "../lib/entities";
import {
  ADME_BOOLEAN_PARAMS,
  ADME_NUMERIC_PARAMS,
  ADME_PARAMS,
  DEFAULT_DISEASE_INPUT_MODE,
  DEFAULT_MODE,
  DEFAULT_PLANT_INPUT_MODE,
  DISEASE_INPUT_MODES,
  DISEASE_TARGETS_NUMERIC_PARAMS,
  DISEASE_TARGETS_PARAMS,
  ENRICHMENT_ARRAY_PARAMS,
  ENRICHMENT_BOOLEAN_PARAMS,
  ENRICHMENT_NUMERIC_PARAMS,
  ENRICHMENT_PARAMS,
  ENRICHMENT_SELECT_PARAMS,
  HUB_GENES_BOOLEAN_PARAMS,
  HUB_GENES_NUMERIC_PARAMS,
  HUB_GENES_PARAMS,
  MAX_PLANTS,
  PLANT_INPUT_MODES,
  PPI_BOOLEAN_PARAMS,
  PPI_NUMERIC_PARAMS,
  PPI_PARAMS,
  PPI_SELECT_PARAMS,
  TARGET_NUMERIC_PARAMS,
  TARGET_PARAMS,
} from "../contract";
import { INPUT_MODE_DESCRIPTIONS } from "../contract/labels";
import { RemovableChipList } from "./RemovableChipList";
import { ParamPanel, type ParamMeta } from "./stages/ParamPanel";
import { CompoundValidateBox } from "./CompoundValidateBox";
import { EntitySearchCombobox, type ComboOption } from "./EntitySearchCombobox";
import { TargetValidateBox } from "./TargetValidateBox";
import { Button } from "./ui/button";
import { Eyebrow, StatNumber } from "./ui/editorial";
import { GlassSurface } from "./ui/GlassSurface";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { RunModeCards } from "./setup/RunModeCards";
import { SegmentedTabs } from "./ui/SegmentedTabs";

// ---------------------------------------------------------------------------
// Param group definitions for the Advanced parameters section.
// Each entry carries the baseline params (built from meta defaults), the
// meta object, and the key arrays needed by ParamPanel.
// ---------------------------------------------------------------------------

type ParamGroupKey = "adme" | "target" | "disease_targets" | "ppi" | "hub_genes" | "enrichment";

type GroupChange = Record<string, number | boolean | string | string[]>;

type ParamGroup = {
  key: ParamGroupKey;
  title: string;
  meta: Record<string, ParamMeta>;
  numericKeys: readonly string[];
  booleanKeys: readonly string[];
  selectKeys: readonly string[];
  arrayKeys: readonly string[];
};

/** Build a panel's baseline params from each meta's `default`, keyed by param name. */
function buildDefaults(
  meta: Record<string, ParamMeta>,
): Record<string, number | boolean | string | string[]> {
  const result: Record<string, number | boolean | string | string[]> = {};
  for (const [k, v] of Object.entries(meta)) {
    result[k] = v.default;
  }
  return result;
}

const PARAM_GROUPS: ParamGroup[] = [
  {
    key: "adme",
    title: "ADME screening",
    meta: ADME_PARAMS,
    numericKeys: ADME_NUMERIC_PARAMS,
    booleanKeys: ADME_BOOLEAN_PARAMS,
    selectKeys: [],
    arrayKeys: [],
  },
  {
    key: "target",
    title: "Target identification",
    meta: TARGET_PARAMS,
    numericKeys: TARGET_NUMERIC_PARAMS,
    booleanKeys: [],
    selectKeys: [],
    arrayKeys: [],
  },
  {
    key: "disease_targets",
    title: "Disease targets",
    meta: DISEASE_TARGETS_PARAMS,
    numericKeys: DISEASE_TARGETS_NUMERIC_PARAMS,
    booleanKeys: [],
    selectKeys: [],
    arrayKeys: [],
  },
  {
    key: "ppi",
    title: "PPI network",
    meta: PPI_PARAMS,
    numericKeys: PPI_NUMERIC_PARAMS,
    booleanKeys: PPI_BOOLEAN_PARAMS,
    selectKeys: PPI_SELECT_PARAMS,
    arrayKeys: [],
  },
  {
    key: "hub_genes",
    title: "Hub genes",
    meta: HUB_GENES_PARAMS,
    numericKeys: HUB_GENES_NUMERIC_PARAMS,
    booleanKeys: HUB_GENES_BOOLEAN_PARAMS,
    selectKeys: [],
    arrayKeys: [],
  },
  {
    key: "enrichment",
    title: "Functional enrichment",
    meta: ENRICHMENT_PARAMS,
    numericKeys: ENRICHMENT_NUMERIC_PARAMS,
    booleanKeys: ENRICHMENT_BOOLEAN_PARAMS,
    selectKeys: ENRICHMENT_SELECT_PARAMS,
    arrayKeys: ENRICHMENT_ARRAY_PARAMS,
  },
];

/**
 * One advanced-parameter group panel. Binds the group's stable `onGroupChange`
 * + key into a single stable `onChange` so ParamPanel's collect-mode effect does
 * not re-fire on every SetupView render.
 */
function AdvancedParamPanel({
  group,
  onGroupChange,
}: {
  group: ParamGroup;
  onGroupChange: (groupKey: ParamGroupKey, changed: GroupChange) => void;
}) {
  const handleChange = useCallback(
    (changed: GroupChange) => onGroupChange(group.key, changed),
    [group.key, onGroupChange],
  );
  return (
    <ParamPanel
      params={buildDefaults(group.meta)}
      meta={group.meta}
      onRedo={() => {}}
      onChange={handleChange}
      hideRedo
      title={group.title}
      numericKeys={group.numericKeys}
      booleanKeys={group.booleanKeys}
      selectKeys={group.selectKeys}
      arrayKeys={group.arrayKeys}
    />
  );
}

// ---------------------------------------------------------------------------
// Form values shape + advisory Zod resolver.
//
// The whole setup form lives in react-hook-form. These are the FORM values
// (selections, pools, labels, overrides) — NOT the wire body. The wire body is
// still assembled in `mutationFn` from `getValues()`.
//
// The resolver is advisory only: the server is authoritative. It does not gate
// the Create button (see `canSubmit`) and does not block `create.mutate()`. It
// just sanity-checks the form-values shape (label lengths, plant count) so RHF's
// `formState.errors` reflects the same soft limits the inputs already enforce.
// We deliberately do NOT bind `zAnalysisCreate` (the all-optional WIRE schema).
// ---------------------------------------------------------------------------

type FormValues = {
  mode: string;
  analysisName: string;
  plantMode: (typeof PLANT_INPUT_MODES)[number];
  diseaseMode: (typeof DISEASE_INPUT_MODES)[number];
  selectedPlants: ComboOption[];
  selectedDisease: ComboOption[];
  resolved: ResolvedCompound[];
  manualTargets: ResolvedTarget[];
  manualDiseaseTargets: ResolvedTarget[];
  plantLabel: string;
  diseaseLabel: string;
  overrides: Record<string, GroupChange>;
};

// The schema covers the whole FormValues shape so the resolver type lines up with
// `useForm<FormValues>`, but only the label lengths and plant count carry real
// (advisory) checks; the structured pools/selections pass through unvalidated.
const formSchema = z.object({
  mode: z.string(),
  analysisName: z.string().max(200),
  plantMode: z.custom<FormValues["plantMode"]>(),
  diseaseMode: z.custom<FormValues["diseaseMode"]>(),
  selectedPlants: z.custom<ComboOption[]>().refine((v) => (v?.length ?? 0) <= MAX_PLANTS, {
    message: `Too many plants (max ${MAX_PLANTS}).`,
  }),
  selectedDisease: z.custom<ComboOption[]>(),
  resolved: z.custom<ResolvedCompound[]>(),
  manualTargets: z.custom<ResolvedTarget[]>(),
  manualDiseaseTargets: z.custom<ResolvedTarget[]>(),
  plantLabel: z.string().max(200),
  diseaseLabel: z.string().max(200),
  overrides: z.custom<Record<string, GroupChange>>(),
});

const DEFAULT_FORM_VALUES: FormValues = {
  mode: DEFAULT_MODE,
  analysisName: "",
  plantMode: DEFAULT_PLANT_INPUT_MODE,
  diseaseMode: DEFAULT_DISEASE_INPUT_MODE,
  selectedPlants: [],
  selectedDisease: [],
  resolved: [],
  manualTargets: [],
  manualDiseaseTargets: [],
  plantLabel: "",
  diseaseLabel: "",
  overrides: {},
};

export function SetupView({ onCreated }: { onCreated: (id: string) => void }) {
  // The setup form is managed by react-hook-form. Children are custom controlled
  // components, so we read live values via `watch()` and write via `setValue()`
  // (RHF's `register` only covers native inputs, which this form barely has).
  const { watch, setValue, getValues } = useForm<FormValues>({
    defaultValues: DEFAULT_FORM_VALUES,
    resolver: zodResolver(formSchema),
    mode: "onChange",
  });

  // Live form values used for rendering + the submit gate.
  const mode = watch("mode");
  const analysisName = watch("analysisName");
  const plantMode = watch("plantMode");
  const diseaseMode = watch("diseaseMode");
  const selectedPlants = watch("selectedPlants");
  const selectedDisease = watch("selectedDisease");
  const resolved = watch("resolved");
  const manualTargets = watch("manualTargets");
  const manualDiseaseTargets = watch("manualDiseaseTargets");
  const plantLabel = watch("plantLabel");
  const diseaseLabel = watch("diseaseLabel");

  // ------- advanced parameter overrides -------
  // `advancedOpen` is UI toggle state, not form data — it stays in useState.
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // Stable collect-mode handler: `setValue`/`getValues` are stable across renders,
  // so the `onChange` identity each ParamPanel receives never changes and the
  // collect-mode effect does not re-fire/loop. `overrides` is not watched (read
  // only at submit), so writing it does not churn renders.
  const handleGroupChange = useCallback(
    (groupKey: ParamGroupKey, changed: GroupChange) => {
      setValue("overrides", { ...getValues("overrides"), [groupKey]: changed });
    },
    [setValue, getValues],
  );

  // ------- search functions for comboboxes -------
  const searchPlants = useCallback(async (q: string): Promise<ComboOption[]> => {
    const { data } = await listPlants({ query: { q: q || undefined, limit: 50 } });
    return (data ?? []).map((p) => ({
      value: p.plant_id,
      label: p.canonical_scientific_name ?? p.plant_id,
      hint: p.matched_alias ?? null,
    }));
  }, []);

  const searchDiseases = useCallback(async (q: string): Promise<ComboOption[]> => {
    const { data } = await listDiseases({ query: { q: q || undefined, limit: 50 } });
    return (data ?? []).map((d) => ({
      value: d.disease_id,
      label: d.disease_name ?? d.disease_id,
      hint: d.matched_alias ?? null,
    }));
  }, []);

  // Build the parameters payload: only include groups with at least one changed value.
  const buildParametersPayload = useCallback((): Record<string, GroupChange> | undefined => {
    const nonEmpty = Object.entries(getValues("overrides")).filter(
      ([, v]) => Object.keys(v).length > 0,
    );
    if (nonEmpty.length === 0) return undefined;
    return Object.fromEntries(nonEmpty) as Record<string, GroupChange>;
  }, [getValues]);

  const create = useMutation({
    mutationFn: async () => {
      const v = getValues();
      const res = await createAnalysis({
        body: {
          analysis_name: v.analysisName.trim() || null,
          plant_input_mode: v.plantMode,
          disease_input_mode: v.diseaseMode,
          mode: v.mode as "auto" | "guided",
          plant_ids: v.plantMode === "selection" ? v.selectedPlants.map((o) => o.value) : [],
          disease_id: v.diseaseMode === "selection" ? (v.selectedDisease[0]?.value ?? null) : null,
          manual_compound_ids:
            v.plantMode === "manual_compounds" ? v.resolved.map((r) => r.compound_id) : [],
          manual_target_ids:
            v.plantMode === "manual_targets" ? v.manualTargets.map((t) => t.target_id) : [],
          manual_disease_target_ids:
            v.diseaseMode === "manual_disease_targets"
              ? v.manualDiseaseTargets.map((t) => t.target_id)
              : [],
          plant_label: v.plantMode === "selection" ? null : v.plantLabel || null,
          disease_label: v.diseaseMode === "selection" ? null : v.diseaseLabel || null,
          parameters: buildParametersPayload(),
        },
      });
      return res.data as AnalysisRead;
    },
    onSuccess: (data) => onCreated(data.analysis_id),
    onError: (error) => notifyError(error as Problem),
  });

  // ------- canSubmit -------
  const plantReady =
    plantMode === "selection"
      ? selectedPlants.length >= 1 && selectedPlants.length <= MAX_PLANTS
      : plantMode === "manual_compounds"
        ? resolved.length >= 1
        : manualTargets.length >= 1;

  const diseaseReady =
    diseaseMode === "selection" ? selectedDisease.length > 0 : manualDiseaseTargets.length >= 1;

  const canSubmit = plantReady && diseaseReady;

  // ------- selection summary (serif roll-up) -------
  const plantCount =
    plantMode === "selection"
      ? selectedPlants.length
      : plantMode === "manual_compounds"
        ? resolved.length
        : manualTargets.length;
  const plantNoun =
    plantMode === "manual_compounds"
      ? "compounds"
      : plantMode === "manual_targets"
        ? "plant targets"
        : plantCount === 1
          ? "plant"
          : "plants";
  const diseaseCount =
    diseaseMode === "selection" ? selectedDisease.length : manualDiseaseTargets.length;
  const diseaseNoun =
    diseaseMode === "selection" ? (diseaseCount === 1 ? "disease" : "diseases") : "disease targets";
  const hasSelection = plantCount > 0 || diseaseCount > 0;

  return (
    <section className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
      <header className="mb-8 space-y-2">
        <Eyebrow>Setup</Eyebrow>
        <h1>New analysis</h1>
      </header>

      <div className="space-y-6">
        {/* ---- Run name ---- */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="analysis-name">Name this analysis</Label>
          <Input
            id="analysis-name"
            value={analysisName}
            onChange={(e) => setValue("analysisName", e.target.value)}
            placeholder="e.g. Curcuma vs Type 2 Diabetes"
            maxLength={200}
          />
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          {/* ---- Plant input ---- */}
          <GlassSurface tier="raised" className="rounded-[var(--radius-lg)] p-5">
            <h2 className="font-display text-hf-fg-1 text-lg tracking-tight">Plant input</h2>
            <div className="mt-4 space-y-5">
              <SegmentedTabs
                value={plantMode}
                onChange={(v) =>
                  setValue("plantMode", v as (typeof PLANT_INPUT_MODES)[number], {
                    shouldValidate: true,
                  })
                }
                options={[
                  {
                    value: "selection",
                    label: "Select plants",
                    description: INPUT_MODE_DESCRIPTIONS["selection"],
                  },
                  {
                    value: "manual_compounds",
                    label: "Enter compounds",
                    description: INPUT_MODE_DESCRIPTIONS["manual_compounds"],
                  },
                  {
                    value: "manual_targets",
                    label: "Enter targets",
                    description: INPUT_MODE_DESCRIPTIONS["manual_targets"],
                  },
                ]}
                ariaLabel="Plant input mode"
              />

              {plantMode === "selection" && (
                <div className="space-y-3">
                  <Label>Search plants</Label>
                  <EntitySearchCombobox
                    mode="multiple"
                    selected={selectedPlants}
                    onChange={(next) => setValue("selectedPlants", next)}
                    search={searchPlants}
                    max={MAX_PLANTS}
                    placeholder="Search plants…"
                    ariaLabel="Search plants"
                  />
                  <p className="text-muted-foreground text-sm">
                    {selectedPlants.length} / {MAX_PLANTS} plants
                  </p>
                  {selectedPlants.length > MAX_PLANTS && (
                    <p role="alert" className="text-destructive text-sm">
                      Too many plants (max {MAX_PLANTS}).
                    </p>
                  )}
                </div>
              )}

              {plantMode === "manual_compounds" && (
                <>
                  <CompoundValidateBox
                    showAddButton
                    onResolved={(incoming) =>
                      setValue(
                        "resolved",
                        mergeById(getValues("resolved"), incoming, "compound_id"),
                      )
                    }
                  />
                  <RemovableChipList
                    items={resolved}
                    getKey={(r) => r.compound_id}
                    getLabel={(r) => r.canonical_name ?? r.canonical_key ?? r.compound_id}
                    onRemove={(r) =>
                      setValue(
                        "resolved",
                        getValues("resolved").filter((x) => x.compound_id !== r.compound_id),
                      )
                    }
                    ariaLabel="Added compounds"
                  />
                </>
              )}

              {plantMode === "manual_targets" && (
                <>
                  <TargetValidateBox
                    label="Plant targets"
                    showAddButton
                    onResolved={(incoming) =>
                      setValue(
                        "manualTargets",
                        mergeById(getValues("manualTargets"), incoming, "target_id"),
                      )
                    }
                  />
                  <RemovableChipList
                    items={manualTargets}
                    getKey={(t) => t.target_id}
                    getLabel={(t) => t.gene_symbol ?? t.uniprot_accession ?? t.canonical_key}
                    onRemove={(t) =>
                      setValue(
                        "manualTargets",
                        getValues("manualTargets").filter((x) => x.target_id !== t.target_id),
                      )
                    }
                    ariaLabel="Added plant targets"
                  />
                </>
              )}

              {plantMode !== "selection" && (
                <div className="space-y-1.5">
                  <Label htmlFor="plant-label">Plant label (optional)</Label>
                  <Input
                    id="plant-label"
                    aria-label="Plant label"
                    value={plantLabel}
                    maxLength={200}
                    onChange={(e) => setValue("plantLabel", e.target.value)}
                    placeholder="Optional label for this plant set"
                  />
                </div>
              )}
            </div>
          </GlassSurface>

          {/* ---- Disease input ---- */}
          <GlassSurface tier="raised" className="rounded-[var(--radius-lg)] p-5">
            <h2 className="font-display text-hf-fg-1 text-lg tracking-tight">Disease input</h2>
            <div className="mt-4 space-y-5">
              <SegmentedTabs
                value={diseaseMode}
                onChange={(v) =>
                  setValue("diseaseMode", v as (typeof DISEASE_INPUT_MODES)[number], {
                    shouldValidate: true,
                  })
                }
                options={[
                  {
                    value: "selection",
                    label: "Select disease",
                    description: INPUT_MODE_DESCRIPTIONS["disease_selection"],
                  },
                  {
                    value: "manual_disease_targets",
                    label: "Enter targets",
                    description: INPUT_MODE_DESCRIPTIONS["manual_disease_targets"],
                  },
                ]}
                ariaLabel="Disease input mode"
              />

              {diseaseMode === "selection" && (
                <div className="space-y-1.5">
                  <Label>Search disease</Label>
                  <EntitySearchCombobox
                    mode="single"
                    selected={selectedDisease}
                    onChange={(next) => setValue("selectedDisease", next)}
                    search={searchDiseases}
                    placeholder="Search disease…"
                    ariaLabel="Search disease"
                  />
                </div>
              )}

              {diseaseMode === "manual_disease_targets" && (
                <>
                  <TargetValidateBox
                    label="Disease targets"
                    showAddButton
                    onResolved={(incoming) =>
                      setValue(
                        "manualDiseaseTargets",
                        mergeById(getValues("manualDiseaseTargets"), incoming, "target_id"),
                      )
                    }
                  />
                  <RemovableChipList
                    items={manualDiseaseTargets}
                    getKey={(t) => t.target_id}
                    getLabel={(t) => t.gene_symbol ?? t.uniprot_accession ?? t.canonical_key}
                    onRemove={(t) =>
                      setValue(
                        "manualDiseaseTargets",
                        getValues("manualDiseaseTargets").filter(
                          (x) => x.target_id !== t.target_id,
                        ),
                      )
                    }
                    ariaLabel="Added disease targets"
                  />
                </>
              )}

              {diseaseMode !== "selection" && (
                <div className="space-y-1.5">
                  <Label htmlFor="disease-label">Disease label (optional)</Label>
                  <Input
                    id="disease-label"
                    aria-label="Disease label"
                    value={diseaseLabel}
                    maxLength={200}
                    onChange={(e) => setValue("diseaseLabel", e.target.value)}
                    placeholder="Optional label for this disease target set"
                  />
                </div>
              )}
            </div>
          </GlassSurface>
        </div>

        {/* ---- Run mode ---- */}
        <GlassSurface tier="raised" className="rounded-[var(--radius-lg)] p-5">
          <h2 className="font-display text-hf-fg-1 text-lg tracking-tight">Run mode</h2>
          <div className="mt-4">
            <RunModeCards
              value={mode as "guided" | "auto"}
              onChange={(v) => setValue("mode", v, { shouldValidate: true })}
            />
          </div>
        </GlassSurface>

        {/* ---- Advanced parameters ---- */}
        <GlassSurface tier="raised" className="rounded-[var(--radius-lg)] p-5">
          <button
            type="button"
            aria-expanded={advancedOpen}
            aria-controls="advanced-params-content"
            className="flex w-full items-center gap-2 text-left"
            onClick={() => setAdvancedOpen((o) => !o)}
          >
            <span className="text-muted-foreground text-xs">{advancedOpen ? "▾" : "▸"}</span>
            <span className="text-sm font-medium">Advanced parameters</span>
          </button>

          {advancedOpen && (
            <div id="advanced-params-content" className="mt-4 flex flex-col gap-4">
              {PARAM_GROUPS.map((group) => (
                <AdvancedParamPanel
                  key={group.key}
                  group={group}
                  onGroupChange={handleGroupChange}
                />
              ))}
            </div>
          )}
        </GlassSurface>

        {/* ---- Selection summary ---- */}
        <GlassSurface
          tier="raised"
          className="rounded-[var(--radius-lg)] p-5"
          data-testid="setup-summary"
        >
          <Eyebrow>Selection</Eyebrow>
          <p className="font-display text-hf-fg-1 mt-2 text-xl">
            {hasSelection ? (
              <>
                <StatNumber>{plantCount}</StatNumber> {plantNoun}
                {" · "}
                <StatNumber>{diseaseCount}</StatNumber> {diseaseNoun}
              </>
            ) : (
              <span className="text-hf-fg-3">Nothing selected yet.</span>
            )}
          </p>
        </GlassSurface>

        <Button
          disabled={!canSubmit || create.isPending}
          onClick={() => create.mutate()}
          className="rounded-[var(--radius-pill)]"
        >
          {create.isPending ? "Starting…" : "Start analysis"}
        </Button>
      </div>
    </section>
  );
}
