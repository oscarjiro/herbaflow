import { useCallback, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { listDiseases, listPlants, createAnalysis } from "../api/sdk.gen";
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
  MODES,
  PLANT_INPUT_MODES,
  PPI_BOOLEAN_PARAMS,
  PPI_NUMERIC_PARAMS,
  PPI_PARAMS,
  PPI_SELECT_PARAMS,
  TARGET_NUMERIC_PARAMS,
  TARGET_PARAMS,
} from "../contract";
import { RemovableChipList } from "./RemovableChipList";
import { ParamPanel, type ParamMeta } from "./stages/ParamPanel";
import { CompoundValidateBox } from "./CompoundValidateBox";
import { EntitySearchCombobox, type ComboOption } from "./EntitySearchCombobox";
import { TargetValidateBox } from "./TargetValidateBox";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Eyebrow } from "./ui/editorial";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { RadioGroup, RadioGroupItem } from "./ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

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

export function SetupView({ onCreated }: { onCreated: (id: string) => void }) {
  // ------- core selection state -------
  const [selectedPlants, setSelectedPlants] = useState<ComboOption[]>([]);
  const [selectedDisease, setSelectedDisease] = useState<ComboOption[]>([]);
  const [mode, setMode] = useState<string>(DEFAULT_MODE);

  // ------- advanced parameter overrides -------
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, GroupChange>>({});

  const handleGroupChange = useCallback((groupKey: ParamGroupKey, changed: GroupChange) => {
    setOverrides((prev) => ({ ...prev, [groupKey]: changed }));
  }, []);

  // ------- input-mode state -------
  const [plantMode, setPlantMode] =
    useState<(typeof PLANT_INPUT_MODES)[number]>(DEFAULT_PLANT_INPUT_MODE);
  const [diseaseMode, setDiseaseMode] = useState<(typeof DISEASE_INPUT_MODES)[number]>(
    DEFAULT_DISEASE_INPUT_MODE,
  );

  // ------- manual-entity state -------
  const [resolved, setResolved] = useState<ResolvedCompound[]>([]); // manual_compounds
  const [manualTargets, setManualTargets] = useState<ResolvedTarget[]>([]); // manual_targets (plant)
  const [manualDiseaseTargets, setManualDiseaseTargets] = useState<ResolvedTarget[]>([]); // manual_disease_targets

  // ------- free-text label state -------
  const [plantLabel, setPlantLabel] = useState("");
  const [diseaseLabel, setDiseaseLabel] = useState("");

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
  const parametersPayload = useMemo(() => {
    const nonEmpty = Object.entries(overrides).filter(([, v]) => Object.keys(v).length > 0);
    if (nonEmpty.length === 0) return undefined;
    return Object.fromEntries(nonEmpty) as Record<string, GroupChange>;
  }, [overrides]);

  const create = useMutation({
    mutationFn: async () => {
      const res = await createAnalysis({
        body: {
          analysis_name: null,
          plant_input_mode: plantMode,
          disease_input_mode: diseaseMode,
          mode: mode as "auto" | "guided",
          plant_ids: plantMode === "selection" ? selectedPlants.map((o) => o.value) : [],
          disease_id: diseaseMode === "selection" ? (selectedDisease[0]?.value ?? null) : null,
          manual_compound_ids:
            plantMode === "manual_compounds" ? resolved.map((r) => r.compound_id) : [],
          manual_target_ids:
            plantMode === "manual_targets" ? manualTargets.map((t) => t.target_id) : [],
          manual_disease_target_ids:
            diseaseMode === "manual_disease_targets"
              ? manualDiseaseTargets.map((t) => t.target_id)
              : [],
          plant_label: plantMode === "selection" ? null : plantLabel || null,
          disease_label: diseaseMode === "selection" ? null : diseaseLabel || null,
          parameters: parametersPayload,
        },
      });
      return res.data as AnalysisRead;
    },
    onSuccess: (data) => onCreated(data.analysis_id),
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

  return (
    <section className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6">
      <header className="mb-8 space-y-2">
        <Eyebrow>Setup</Eyebrow>
        <h1>New analysis</h1>
      </header>

      <div className="space-y-6">
        {/* ---- Plant input ---- */}
        <Card>
          <CardHeader>
            <CardTitle>Plant input</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <fieldset className="space-y-3">
              <legend className="hf-eyebrow mb-2">Plant input mode</legend>
              <RadioGroup
                value={plantMode}
                onValueChange={(v) => setPlantMode(v as (typeof PLANT_INPUT_MODES)[number])}
              >
                {PLANT_INPUT_MODES.map((m) => (
                  <div key={m} className="flex items-center gap-2">
                    <RadioGroupItem id={`plant-mode-${m}`} value={m} aria-label={m} />
                    <Label htmlFor={`plant-mode-${m}`} className="font-normal">
                      {m}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </fieldset>

            {plantMode === "selection" && (
              <div className="space-y-3">
                <Label>Search plants</Label>
                <EntitySearchCombobox
                  mode="multiple"
                  selected={selectedPlants}
                  onChange={setSelectedPlants}
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
                    setResolved((prev) => mergeById(prev, incoming, "compound_id"))
                  }
                />
                <RemovableChipList
                  items={resolved}
                  getKey={(r) => r.compound_id}
                  getLabel={(r) => r.canonical_name ?? r.canonical_key ?? r.compound_id}
                  onRemove={(r) =>
                    setResolved((prev) => prev.filter((x) => x.compound_id !== r.compound_id))
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
                    setManualTargets((prev) => mergeById(prev, incoming, "target_id"))
                  }
                />
                <RemovableChipList
                  items={manualTargets}
                  getKey={(t) => t.target_id}
                  getLabel={(t) => t.gene_symbol ?? t.uniprot_accession ?? t.canonical_key}
                  onRemove={(t) =>
                    setManualTargets((prev) => prev.filter((x) => x.target_id !== t.target_id))
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
                  onChange={(e) => setPlantLabel(e.target.value)}
                  placeholder="Optional label for this plant set"
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---- Disease input ---- */}
        <Card>
          <CardHeader>
            <CardTitle>Disease input</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <fieldset className="space-y-3">
              <legend className="hf-eyebrow mb-2">Disease input mode</legend>
              <RadioGroup
                value={diseaseMode}
                onValueChange={(v) => setDiseaseMode(v as (typeof DISEASE_INPUT_MODES)[number])}
              >
                {DISEASE_INPUT_MODES.map((m) => (
                  <div key={m} className="flex items-center gap-2">
                    <RadioGroupItem id={`disease-mode-${m}`} value={m} aria-label={m} />
                    <Label htmlFor={`disease-mode-${m}`} className="font-normal">
                      {m}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </fieldset>

            {diseaseMode === "selection" && (
              <div className="space-y-1.5">
                <Label>Search disease</Label>
                <EntitySearchCombobox
                  mode="single"
                  selected={selectedDisease}
                  onChange={setSelectedDisease}
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
                    setManualDiseaseTargets((prev) => mergeById(prev, incoming, "target_id"))
                  }
                />
                <RemovableChipList
                  items={manualDiseaseTargets}
                  getKey={(t) => t.target_id}
                  getLabel={(t) => t.gene_symbol ?? t.uniprot_accession ?? t.canonical_key}
                  onRemove={(t) =>
                    setManualDiseaseTargets((prev) =>
                      prev.filter((x) => x.target_id !== t.target_id),
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
                  onChange={(e) => setDiseaseLabel(e.target.value)}
                  placeholder="Optional label for this disease target set"
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---- Mode (auto/guided) ---- */}
        <Card>
          <CardHeader>
            <CardTitle>Mode</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              <Label htmlFor="mode">Mode</Label>
              <Select value={mode} onValueChange={setMode}>
                <SelectTrigger id="mode" aria-label="Mode" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODES.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* ---- Advanced parameters ---- */}
        <div>
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
        </div>

        <Button
          disabled={!canSubmit || create.isPending}
          onClick={() => create.mutate()}
          className="w-full sm:w-auto"
        >
          Create analysis
        </Button>
      </div>
    </section>
  );
}
