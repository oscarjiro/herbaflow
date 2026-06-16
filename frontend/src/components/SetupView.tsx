import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { listDiseasesOptions, listPlantsOptions } from "../api/@tanstack/react-query.gen";
import { createAnalysis } from "../api/sdk.gen";
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
import { TargetValidateBox } from "./TargetValidateBox";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Checkbox } from "./ui/checkbox";
import { Eyebrow } from "./ui/editorial";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { RadioGroup, RadioGroupItem } from "./ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

export function SetupView({ onCreated }: { onCreated: (id: string) => void }) {
  const diseases = useQuery(listDiseasesOptions());
  const plants = useQuery(listPlantsOptions());

  // ------- core selection state -------
  const [selected, setSelected] = useState<string[]>([]);
  const [diseaseId, setDiseaseId] = useState<string>("");
  const [mode, setMode] = useState<string>(DEFAULT_MODE);
  const [filter, setFilter] = useState("");

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

  const create = useMutation({
    mutationFn: async () => {
      const res = await createAnalysis({
        body: {
          analysis_name: null,
          plant_input_mode: plantMode,
          disease_input_mode: diseaseMode,
          mode: mode as "auto" | "guided",
          plant_ids: plantMode === "selection" ? selected : [],
          disease_id: diseaseMode === "selection" ? diseaseId : null,
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
      ? selected.length >= 1 && selected.length <= MAX_PLANTS
      : plantMode === "manual_compounds"
        ? resolved.length >= 1
        : manualTargets.length >= 1;

  const diseaseReady =
    diseaseMode === "selection" ? diseaseId !== "" : manualDiseaseTargets.length >= 1;

  const canSubmit = plantReady && diseaseReady;

  const filteredPlants = plants.data
    ?.filter((p) =>
      (p.canonical_scientific_name ?? "").toLowerCase().includes(filter.toLowerCase()),
    )
    .slice(0, 100);

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
                <div className="space-y-1.5">
                  <Label htmlFor="plant-filter">Filter plants</Label>
                  <Input
                    id="plant-filter"
                    aria-label="Filter plants"
                    placeholder="Filter plants"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  />
                </div>
                <p className="text-muted-foreground text-sm">
                  {selected.length} / {MAX_PLANTS} plants
                </p>
                {selected.length > MAX_PLANTS && (
                  <p role="alert" className="text-destructive text-sm">
                    Too many plants (max {MAX_PLANTS}).
                  </p>
                )}
                <ul className="max-h-72 space-y-1 overflow-y-auto rounded-md border p-2">
                  {filteredPlants?.map((p) => (
                    <li key={p.plant_id}>
                      <label className="hover:bg-accent/50 flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm">
                        <Checkbox
                          checked={selected.includes(p.plant_id)}
                          onCheckedChange={(checked) =>
                            setSelected((s) =>
                              checked === true
                                ? [...s, p.plant_id]
                                : s.filter((x) => x !== p.plant_id),
                            )
                          }
                        />
                        {p.canonical_scientific_name}
                      </label>
                    </li>
                  ))}
                </ul>
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
                <Label htmlFor="disease">Disease</Label>
                <Select value={diseaseId} onValueChange={setDiseaseId}>
                  <SelectTrigger id="disease" aria-label="Disease" className="w-full">
                    <SelectValue placeholder="Select a disease" />
                  </SelectTrigger>
                  <SelectContent>
                    {diseases.data?.map((d) => (
                      <SelectItem key={d.disease_id} value={d.disease_id}>
                        {d.disease_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
