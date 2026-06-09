import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { listDiseasesOptions, listPlantsOptions } from "../api/@tanstack/react-query.gen";
import { createAnalysis } from "../api/sdk.gen";
import type { AnalysisRead, ResolvedCompound } from "../api/types.gen";
import { DEFAULT_MODE, MAX_PLANTS, MODES } from "../contract";
import { CompoundValidateBox } from "./CompoundValidateBox";

export function SetupView({ onCreated }: { onCreated: (id: string) => void }) {
  const diseases = useQuery(listDiseasesOptions());
  const plants = useQuery(listPlantsOptions());
  const [selected, setSelected] = useState<string[]>([]);
  const [diseaseId, setDiseaseId] = useState<string>("");
  const [mode, setMode] = useState<string>(DEFAULT_MODE);
  const [filter, setFilter] = useState("");

  const [resolved, setResolved] = useState<ResolvedCompound[]>([]);

  const create = useMutation({
    mutationFn: async () => {
      const res = await createAnalysis({
        body: {
          plant_ids: selected,
          disease_id: diseaseId,
          mode: mode as "auto" | "guided",
          manual_compound_ids: resolved.map((r) => r.compound_id),
        },
      });
      return res.data as AnalysisRead;
    },
    onSuccess: (data) => onCreated(data.analysis_id),
  });

  const overCap = selected.length > MAX_PLANTS;
  const canSubmit = selected.length >= 1 && !overCap && diseaseId !== "";

  return (
    <section>
      <h1>New analysis</h1>

      <label htmlFor="disease">Disease</label>
      <select id="disease" value={diseaseId} onChange={(e) => setDiseaseId(e.target.value)}>
        <option value="">Select a disease</option>
        {diseases.data?.map((d) => (
          <option key={d.disease_id} value={d.disease_id}>
            {d.disease_name}
          </option>
        ))}
      </select>

      <label htmlFor="mode">Mode</label>
      <select id="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
        {MODES.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>

      <input
        aria-label="Filter plants"
        placeholder="Filter plants"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <p>
        {selected.length} / {MAX_PLANTS} plants
      </p>
      {overCap && <p role="alert">Too many plants (max {MAX_PLANTS}).</p>}

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

      <CompoundValidateBox onResolved={setResolved} />

      <button disabled={!canSubmit || create.isPending} onClick={() => create.mutate()}>
        Create analysis
      </button>
    </section>
  );
}
