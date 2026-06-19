import { useCallback, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { listDiseases, listPlants, createAnalysis } from "../api/sdk.gen";
import type { AnalysisRead, ResolvedCompound, ResolvedTarget } from "../api/types.gen";
import {
  DEFAULT_DISEASE_INPUT_MODE,
  DEFAULT_MODE,
  DEFAULT_PLANT_INPUT_MODE,
  DISEASE_INPUT_MODES,
  MAX_PLANTS,
  MODES,
  PLANT_INPUT_MODES,
} from "../contract";
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

export function SetupView({ onCreated }: { onCreated: (id: string) => void }) {
  // ------- core selection state -------
  const [selectedPlants, setSelectedPlants] = useState<ComboOption[]>([]);
  const [selectedDisease, setSelectedDisease] = useState<ComboOption[]>([]);
  const [mode, setMode] = useState<string>(DEFAULT_MODE);

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

            {plantMode === "manual_compounds" && <CompoundValidateBox onResolved={setResolved} />}

            {plantMode === "manual_targets" && (
              <TargetValidateBox label="Plant targets" onResolved={setManualTargets} />
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
              <TargetValidateBox label="Disease targets" onResolved={setManualDiseaseTargets} />
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
