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

  return (
    <section>
      <h1>New analysis</h1>

      {/* ---- Plant input mode ---- */}
      <fieldset>
        <legend>Plant input mode</legend>
        {PLANT_INPUT_MODES.map((m) => (
          <label key={m}>
            <input
              type="radio"
              name="plant_input_mode"
              value={m}
              checked={plantMode === m}
              onChange={() => setPlantMode(m)}
              aria-label={m}
            />
            {m}
          </label>
        ))}
      </fieldset>

      {plantMode === "selection" && (
        <>
          <input
            aria-label="Filter plants"
            placeholder="Filter plants"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <p>
            {selected.length} / {MAX_PLANTS} plants
          </p>
          {selected.length > MAX_PLANTS && <p role="alert">Too many plants (max {MAX_PLANTS}).</p>}
          <ul>
            {plants.data
              ?.filter((p) =>
                (p.canonical_scientific_name ?? "").toLowerCase().includes(filter.toLowerCase()),
              )
              .slice(0, 100)
              .map((p) => (
                <li key={p.plant_id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selected.includes(p.plant_id)}
                      onChange={(e) =>
                        setSelected((s) =>
                          e.target.checked ? [...s, p.plant_id] : s.filter((x) => x !== p.plant_id),
                        )
                      }
                    />
                    {p.canonical_scientific_name}
                  </label>
                </li>
              ))}
          </ul>
        </>
      )}

      {plantMode === "manual_compounds" && <CompoundValidateBox onResolved={setResolved} />}

      {plantMode === "manual_targets" && (
        <TargetValidateBox label="Plant targets" onResolved={setManualTargets} />
      )}

      {plantMode !== "selection" && (
        <label>
          Plant label (optional)
          <input
            aria-label="Plant label"
            value={plantLabel}
            maxLength={200}
            onChange={(e) => setPlantLabel(e.target.value)}
            placeholder="Optional label for this plant set"
          />
        </label>
      )}

      {/* ---- Disease input mode ---- */}
      <fieldset>
        <legend>Disease input mode</legend>
        {DISEASE_INPUT_MODES.map((m) => (
          <label key={m}>
            <input
              type="radio"
              name="disease_input_mode"
              value={m}
              checked={diseaseMode === m}
              onChange={() => setDiseaseMode(m)}
              aria-label={m}
            />
            {m}
          </label>
        ))}
      </fieldset>

      {diseaseMode === "selection" && (
        <>
          <label htmlFor="disease">Disease</label>
          <select id="disease" value={diseaseId} onChange={(e) => setDiseaseId(e.target.value)}>
            <option value="">Select a disease</option>
            {diseases.data?.map((d) => (
              <option key={d.disease_id} value={d.disease_id}>
                {d.disease_name}
              </option>
            ))}
          </select>
        </>
      )}

      {diseaseMode === "manual_disease_targets" && (
        <TargetValidateBox label="Disease targets" onResolved={setManualDiseaseTargets} />
      )}

      {diseaseMode !== "selection" && (
        <label>
          Disease label (optional)
          <input
            aria-label="Disease label"
            value={diseaseLabel}
            maxLength={200}
            onChange={(e) => setDiseaseLabel(e.target.value)}
            placeholder="Optional label for this disease target set"
          />
        </label>
      )}

      {/* ---- Mode (auto/guided) ---- */}
      <label htmlFor="mode">Mode</label>
      <select id="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
        {MODES.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>

      <button disabled={!canSubmit || create.isPending} onClick={() => create.mutate()}>
        Create analysis
      </button>
    </section>
  );
}
