import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { listDiseasesOptions, listPlantsOptions } from "../api/@tanstack/react-query.gen";
import { createAnalysis, validateCompounds } from "../api/sdk.gen";
import type {
  AnalysisRead,
  ResolvedCompound,
  FailedInput,
  ValidateResponse,
} from "../api/types.gen";
import { DEFAULT_MODE, MAX_PLANTS, MODES } from "../contract";

export function SetupView({ onCreated }: { onCreated: (id: string) => void }) {
  const diseases = useQuery(listDiseasesOptions());
  const plants = useQuery(listPlantsOptions());
  const [selected, setSelected] = useState<string[]>([]);
  const [diseaseId, setDiseaseId] = useState<string>("");
  const [mode, setMode] = useState<string>(DEFAULT_MODE);
  const [filter, setFilter] = useState("");

  const [manualText, setManualText] = useState("");
  const [resolved, setResolved] = useState<ResolvedCompound[]>([]);
  const [failed, setFailed] = useState<FailedInput[]>([]);

  const validate = useMutation({
    mutationFn: async () => {
      const lines = manualText
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);
      const inputs = lines.map((value) => ({ value }));
      const res = await validateCompounds({ body: { inputs } });
      return res.data as unknown as ValidateResponse;
    },
    onSuccess: (data) => {
      setResolved(data?.resolved ?? []);
      setFailed(data?.failed ?? []);
    },
  });

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

      <label htmlFor="manual-compounds">Manual compounds</label>
      <textarea
        id="manual-compounds"
        aria-label="Manual compounds"
        value={manualText}
        onChange={(e) => setManualText(e.target.value)}
        placeholder="One SMILES or InChIKey per line"
      />
      <button disabled={validate.isPending} onClick={() => validate.mutate()}>
        Validate
      </button>

      {resolved.length > 0 && (
        <ul aria-label="Resolved compounds">
          {resolved.map((r) => (
            <li key={r.compound_id}>
              {r.canonical_name ?? r.canonical_key}
              {r.validation_status === "structure_only" && " (structure only)"}
            </li>
          ))}
        </ul>
      )}

      {failed.length > 0 && (
        <ul aria-label="Failed inputs">
          {failed.map((f) => (
            <li key={f.value}>
              {f.value}: {f.reason}
            </li>
          ))}
        </ul>
      )}

      <button disabled={!canSubmit || create.isPending} onClick={() => create.mutate()}>
        Create analysis
      </button>
    </section>
  );
}
