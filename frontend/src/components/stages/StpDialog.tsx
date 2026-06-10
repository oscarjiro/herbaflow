/**
 * StpDialog — SwissTargetPrediction (STP) paste-back helper.
 *
 * Lets the user fill coverage gaps for compounds that ChEMBL / PubChem BioAssay
 * could not cover, by running them through SwissTargetPrediction externally and
 * pasting the result CSV back in.
 *
 * Flow:
 *  1. Pick one or more compounds (sorted least-covered-first; 0-coverage on top).
 *  2. Copy their SMILES to the clipboard and open SwissTargetPrediction.
 *  3. Paste the STP result CSV; it is parsed (parseStpCsv) at the chosen
 *     probability threshold and previewed.
 *  4. Import → POST /import-stp-targets for the selected compounds.
 */

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { importStpTargets } from "../../api/sdk.gen";
import type { StpImportResponse } from "../../api/types.gen";
import { parseStpCsv, type StpRow } from "../../lib/stp";

const STP_URL = "http://www.swisstargetprediction.ch/";

export type StpCompound = {
  compound_id: string;
  canonical_name: string | null;
  smiles: string | null;
};

export function StpDialog({
  analysisId,
  compounds,
  perCompound,
}: {
  analysisId: string;
  compounds: StpCompound[];
  perCompound: Record<string, { coverage: number }>;
}) {
  const qc = useQueryClient();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [threshold, setThreshold] = useState(0.6);
  const [pasteText, setPasteText] = useState("");
  const [copyNote, setCopyNote] = useState<string | null>(null);

  // Least-covered first (0-coverage on top), tie-break on name for stability.
  const sorted = useMemo(() => {
    return [...compounds].sort((a, b) => {
      const ca = perCompound[a.compound_id]?.coverage ?? 0;
      const cb = perCompound[b.compound_id]?.coverage ?? 0;
      if (ca !== cb) return ca - cb;
      return (a.canonical_name ?? a.compound_id).localeCompare(b.canonical_name ?? b.compound_id);
    });
  }, [compounds, perCompound]);

  const parse = useMemo(() => parseStpCsv(pasteText, threshold), [pasteText, threshold]);
  const parsedRows: StpRow[] = parse.error ? [] : parse.rows;

  const importMut = useMutation({
    mutationFn: async () => {
      const res = await importStpTargets({
        path: { analysis_id: analysisId },
        body: { compound_ids: Array.from(selected), rows: parsedRows },
      });
      return res.data as unknown as StpImportResponse;
    },
    onSuccess: () => {
      qc.invalidateQueries();
      setSelected(new Set());
      setPasteText("");
    },
  });

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleCopySmiles() {
    const chosen = sorted.filter((c) => selected.has(c.compound_id));
    const withSmiles = chosen.filter((c) => c.smiles);
    const skipped = chosen.length - withSmiles.length;
    const smiles = withSmiles.map((c) => c.smiles).join("\n");
    try {
      await navigator.clipboard.writeText(smiles);
      setCopyNote(
        `Copied ${withSmiles.length} SMILES${skipped > 0 ? ` (${skipped} skipped — no SMILES)` : ""}.`,
      );
    } catch {
      setCopyNote("Copy failed — your browser blocked clipboard access.");
    }
  }

  const canImport = selected.size > 0 && parsedRows.length > 0 && !importMut.isPending;
  const result = importMut.data;

  return (
    <section className="stp-dialog" aria-label="SwissTargetPrediction import">
      <h3>SwissTargetPrediction (manual paste-back)</h3>
      <p className="hf-muted">
        Pick the least-covered compounds, copy their SMILES into SwissTargetPrediction, then paste
        the result CSV here to add predicted targets.
      </p>

      {/* Compound picker — least-covered first */}
      <ul className="stp-compound-list" aria-label="Compounds to screen">
        {sorted.map((c) => {
          const coverage = perCompound[c.compound_id]?.coverage ?? 0;
          return (
            <li key={c.compound_id}>
              <label>
                <input
                  type="checkbox"
                  aria-label={`Select ${c.canonical_name ?? c.compound_id}`}
                  checked={selected.has(c.compound_id)}
                  onChange={() => toggle(c.compound_id)}
                />{" "}
                {c.canonical_name ?? c.compound_id}{" "}
                <span className="hf-caption">coverage {coverage}</span>
                {!c.smiles && <span className="hf-caption"> (no SMILES)</span>}
              </label>
            </li>
          );
        })}
      </ul>

      <div className="stp-actions">
        <button
          type="button"
          className="hf-btn hf-btn-ghost"
          disabled={selected.size === 0}
          onClick={handleCopySmiles}
        >
          Copy SMILES
        </button>
        <a href={STP_URL} target="_blank" rel="noopener noreferrer" className="hf-btn hf-btn-ghost">
          Open SwissTargetPrediction
        </a>
      </div>
      {copyNote && <p className="hf-caption">{copyNote}</p>}

      {/* Threshold + paste-back */}
      <div className="stp-paste">
        <label htmlFor="stp-threshold">Probability threshold</label>
        <input
          id="stp-threshold"
          type="number"
          step="0.05"
          min="0"
          max="1"
          aria-label="Probability threshold"
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
        />
        <label htmlFor="stp-paste">Paste SwissTargetPrediction CSV</label>
        <textarea
          id="stp-paste"
          aria-label="Paste SwissTargetPrediction CSV"
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          placeholder="Uniprot ID,Common name,Probability&#10;..."
          rows={6}
        />
      </div>

      {parse.error && pasteText.trim().length > 0 && (
        <p className="hf-error" role="alert">
          {parse.error}
        </p>
      )}

      {parsedRows.length > 0 && (
        <div className="stp-preview">
          <p className="hf-caption">{parsedRows.length} rows at or above threshold</p>
          <table className="hf-table">
            <thead>
              <tr>
                <th>UniProt</th>
                <th>Common name</th>
                <th>Probability</th>
              </tr>
            </thead>
            <tbody>
              {parsedRows.map((r) => (
                <tr key={r.uniprot}>
                  <td>{r.uniprot}</td>
                  <td>{r.common_name ?? "—"}</td>
                  <td>{r.probability.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <button
        type="button"
        className="hf-btn hf-btn-primary"
        disabled={!canImport}
        onClick={() => importMut.mutate()}
      >
        Import
      </button>

      {result && (
        <p className="stp-import-result" role="status">
          Imported {result.imported}; skipped (already measured) {result.skipped_measured}; failed{" "}
          {result.failed.length}.
        </p>
      )}
    </section>
  );
}
