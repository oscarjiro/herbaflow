/**
 * StpDialog — SwissTargetPrediction (STP) paste-back helper.
 *
 * Lets the user fill coverage gaps for compounds that ChEMBL / PubChem BioAssay
 * could not cover, by running them through SwissTargetPrediction externally and
 * pasting the result CSV back in.
 *
 * Flow:
 *  1. Pick one or more compounds (sorted by target coverage; 0-coverage on top).
 *  2. Copy their SMILES to the clipboard and open SwissTargetPrediction.
 *  3. Paste the STP result CSV; it is parsed (parseStpCsv) at the chosen
 *     probability threshold and previewed.
 *  4. Import -> the pasted accessions are resolved via POST /targets/validate and the
 *     resolved targets are added to the run's Step-3 target set, exactly like a
 *     manual target add. STP is user-asserted, so NO canonical compound→target edge
 *     is written; the targets are run-scoped only.
 *
 * The compound picker is purely a convenience for copying SMILES into STP; it does
 * not scope the import (the resolved targets join the run's flat target set).
 */

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { validateTargets } from "../../api/sdk.gen";
import type { ResolvedTarget, ValidateTargetsResponse } from "../../api/types.gen";
import { humanizeProblem } from "../../lib/problem";
import { parseStpCsv, type StpRow } from "../../lib/stp";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

const STP_URL = "http://www.swisstargetprediction.ch/";

export type StpCompound = {
  compound_id: string;
  canonical_name: string | null;
  smiles: string | null;
};

type ImportSummary = { added: number; alreadyInRun: number; failed: number };

export function StpDialog({
  compounds,
  perCompound,
  existingTargetIds,
  onAddTargets,
}: {
  compounds: StpCompound[];
  perCompound: Record<string, { coverage: number }>;
  existingTargetIds: string[];
  onAddTargets: (resolved: ResolvedTarget[]) => void;
}) {
  const [open, setOpen] = useState(false);
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

  const existing = useMemo(() => new Set(existingTargetIds), [existingTargetIds]);

  const importMut = useMutation({
    mutationFn: async (): Promise<ImportSummary> => {
      // Resolve the pasted accessions through the SAME path as a manual target add.
      const res = await validateTargets({
        body: {
          inputs: parsedRows.map((r) => ({ type: "uniprot" as const, value: r.uniprot })),
        },
      });
      const data = res.data as unknown as ValidateTargetsResponse;
      const resolved = data?.resolved ?? [];
      const failed = data?.failed ?? [];
      // Only add targets not already in the run's set (the edit layer de-dupes too).
      const fresh = resolved.filter((t) => !existing.has(t.target_id));
      if (fresh.length > 0) onAddTargets(fresh);
      return {
        added: fresh.length,
        alreadyInRun: resolved.length - fresh.length,
        failed: failed.length,
      };
    },
    onSuccess: () => {
      setSelected(new Set());
      setPasteText("");
    },
    onError: (error) => {
      toast.error(humanizeProblem(error as Parameters<typeof humanizeProblem>[0]));
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
        skipped > 0
          ? `Copied ${withSmiles.length} SMILES. ${skipped} skipped because no SMILES were available.`
          : `Copied ${withSmiles.length} SMILES.`,
      );
    } catch {
      setCopyNote("Copy failed. Your browser blocked clipboard access.");
    }
  }

  const canImport = parsedRows.length > 0 && !importMut.isPending;
  const result = importMut.data;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          Add SwissTargetPrediction targets
        </Button>
      </DialogTrigger>
      <DialogContent
        className="max-h-[85vh] max-w-2xl overflow-y-auto"
        aria-label="Add targets from SwissTargetPrediction"
      >
        <DialogHeader>
          <DialogTitle>Add targets from SwissTargetPrediction</DialogTitle>
        </DialogHeader>

        <p className="text-sm [color:var(--hf-fg-3)]">
          Select compounds with few target matches, copy their SMILES into SwissTargetPrediction,
          then paste the CSV here. New targets are added only to this analysis.
        </p>

        {/* Compound picker: lowest coverage first (copy-SMILES convenience only). */}
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 text-sm font-medium">Compounds to screen</legend>
          <ul aria-label="Compounds to screen" className="flex flex-col gap-1">
            {sorted.map((c) => {
              const coverage = perCompound[c.compound_id]?.coverage ?? 0;
              return (
                <li key={c.compound_id} className="list-none">
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      aria-label={`Select ${c.canonical_name ?? c.compound_id}`}
                      checked={selected.has(c.compound_id)}
                      onChange={() => toggle(c.compound_id)}
                      className="h-4 w-4 rounded [accent-color:var(--hf-accent)]"
                    />
                    <span>{c.canonical_name ?? c.compound_id}</span>
                    <span className="text-xs [color:var(--hf-fg-3)]">coverage {coverage}</span>
                    {!c.smiles && (
                      <span className="text-xs [color:var(--hf-fg-3)]">(no SMILES)</span>
                    )}
                  </label>
                </li>
              );
            })}
          </ul>
        </fieldset>

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={selected.size === 0}
            onClick={handleCopySmiles}
          >
            Copy SMILES
          </Button>
          <Button type="button" variant="ghost" size="sm" asChild>
            <a href={STP_URL} target="_blank" rel="noopener noreferrer">
              Open SwissTargetPrediction
            </a>
          </Button>
        </div>
        {copyNote && <p className="text-xs [color:var(--hf-fg-3)]">{copyNote}</p>}

        <Separator />

        {/* Threshold + paste-back */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Label htmlFor="stp-threshold" className="shrink-0">
              Probability threshold
            </Label>
            <Input
              id="stp-threshold"
              type="number"
              step="0.05"
              min="0"
              max="1"
              aria-label="Probability threshold"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-28"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="stp-paste">Paste SwissTargetPrediction CSV</Label>
            <Textarea
              id="stp-paste"
              aria-label="Paste SwissTargetPrediction CSV"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder={"Target,Common name,Uniprot ID,...,Probability*,...\n..."}
              rows={6}
            />
          </div>
        </div>

        {parse.error && pasteText.trim().length > 0 && (
          <p className="text-destructive text-sm" role="alert">
            {parse.error} Expected SwissTargetPrediction columns include <code>Uniprot ID</code>,{" "}
            <code>Common name</code>, and <code>Probability*</code>.
          </p>
        )}

        {parsedRows.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-xs [color:var(--hf-fg-3)]">
              {parsedRows.length} rows at or above threshold
            </p>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="border-b [background:var(--hf-surface-1)]">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">UniProt</th>
                    <th className="px-3 py-2 text-left font-medium">Common name</th>
                    <th className="px-3 py-2 text-left font-medium">Probability</th>
                  </tr>
                </thead>
                <tbody>
                  {parsedRows.map((r) => (
                    <tr key={r.uniprot} className="border-b last:border-0">
                      <td className="px-3 py-2">{r.uniprot}</td>
                      <td className="px-3 py-2">{r.common_name ?? "—"}</td>
                      <td className="px-3 py-2">{r.probability.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button type="button" disabled={!canImport} onClick={() => importMut.mutate()}>
            Import
          </Button>
          {!canImport && !importMut.isPending && (
            <span className="text-sm [color:var(--hf-fg-3)]">Paste a valid CSV to import</span>
          )}
        </div>

        {result && (
          <p className="text-sm" role="status">
            Added {result.added} {result.added === 1 ? "target" : "targets"}. {result.alreadyInRun}{" "}
            {result.alreadyInRun === 1 ? "was" : "were"} already present. {result.failed} could not
            be matched.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
