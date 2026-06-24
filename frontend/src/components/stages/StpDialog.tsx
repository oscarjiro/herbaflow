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
 *  4. Import -> the pasted accessions are resolved via POST /targets/validate. Fresh
 *     targets are added to the run's Step-3 target set, and all resolved targets are
 *     linked to the selected compound inside the analysis run only. STP is user-asserted,
 *     so NO canonical database compound-target edge is written.
 *
 * The compound picker scopes the run-local STP links and also copies the selected SMILES.
 */

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Check, Copy, ExternalLink, Search, X } from "lucide-react";
import { validateTargets } from "../../api/sdk.gen";
import type { ResolvedTarget, ValidateTargetsResponse } from "../../api/types.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifySuccess } from "../../lib/toast";
import { parseStpCsv, type StpRow } from "../../lib/stp";
import { Button } from "@/components/ui/button";
import { SourceIconLink } from "@/components/ui/SourceIconLink";
import { StatefulButton } from "@/components/ui/StatefulButton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
  source_url?: string | null;
};

export type StpLinkContext = {
  compoundId: string;
  targetIds: string[];
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
  onAddTargets: (resolved: ResolvedTarget[], link?: StpLinkContext) => void;
}) {
  const [open, setOpen] = useState(false);
  const [selectedCompoundId, setSelectedCompoundId] = useState<string | null>(null);
  const [compoundQuery, setCompoundQuery] = useState("");
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

  const filteredCompounds = useMemo(() => {
    const query = compoundQuery.trim().toLowerCase();
    if (!query) return sorted;
    return sorted.filter((compound) =>
      (compound.canonical_name ?? "").toLowerCase().includes(query),
    );
  }, [sorted, compoundQuery]);

  const parse = useMemo(() => parseStpCsv(pasteText, threshold), [pasteText, threshold]);
  const parsedRows: StpRow[] = parse.error ? [] : parse.rows;
  const selectedCompound = useMemo(
    () => sorted.find((compound) => compound.compound_id === selectedCompoundId) ?? null,
    [sorted, selectedCompoundId],
  );

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
      if (selectedCompoundId && resolved.length > 0) {
        onAddTargets(fresh, {
          compoundId: selectedCompoundId,
          targetIds: resolved.map((t) => t.target_id),
        });
      }
      return {
        added: fresh.length,
        alreadyInRun: resolved.length - fresh.length,
        failed: failed.length,
      };
    },
    onSuccess: (summary) => {
      setSelectedCompoundId(null);
      setPasteText("");
      notifySuccess(`Imported ${summary.added} targets`);
    },
    onError: (error) => notifyError(error as Problem),
  });

  async function handleCopySmiles() {
    if (!selectedCompound?.smiles) {
      setCopyNote("Selected compound has no SMILES to copy.");
      return;
    }
    const label = selectedCompound.canonical_name ?? selectedCompound.compound_id;
    try {
      await navigator.clipboard.writeText(selectedCompound.smiles);
      setCopyNote(`Copied SMILES for ${label}.`);
    } catch {
      setCopyNote("Copy failed. Your browser blocked clipboard access.");
    }
  }

  const canImport = Boolean(selectedCompoundId) && parsedRows.length > 0 && !importMut.isPending;
  const parsedTargetLabel = `${parsedRows.length} protein ${
    parsedRows.length === 1 ? "target" : "targets"
  } read from CSV at or above threshold.`;
  const result = importMut.data;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          Add SwissTargetPrediction targets
        </Button>
      </DialogTrigger>
      <DialogContent
        className="flex max-h-[calc(100vh-2rem)] w-[min(1040px,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] flex-col overflow-hidden sm:max-w-5xl"
        aria-label="Add targets from SwissTargetPrediction"
      >
        <DialogHeader>
          <DialogTitle>Add targets from SwissTargetPrediction</DialogTitle>
          <DialogDescription>
            Select one compound with few target matches, copy its SMILES into SwissTargetPrediction,
            then paste the CSV here. New targets are added only to this analysis.
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-0 flex-col gap-4">
          {/* Compound picker: lowest coverage first (copy-SMILES convenience only). */}
          <fieldset aria-label="Compounds to screen" className="flex min-h-0 flex-col gap-3">
            <div className="flex items-center justify-between gap-3">
              <legend className="text-sm font-medium">Compounds to screen</legend>
              <span className="text-xs [color:var(--hf-fg-3)] tabular-nums">
                {selectedCompoundId ? 1 : 0} selected
              </span>
            </div>
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 [color:var(--hf-fg-3)]"
              />
              <Input
                id="stp-compound-search"
                type="search"
                aria-label="Search compounds"
                value={compoundQuery}
                onChange={(e) => setCompoundQuery(e.target.value)}
                placeholder="Search by name"
                className="pl-8"
              />
            </div>
            <div
              role="region"
              aria-label="Selectable compounds"
              className="scroll border-hf-border bg-hf-bg max-h-56 overflow-x-hidden rounded-md border"
            >
              <table className="w-full table-fixed text-sm">
                <colgroup>
                  <col className="w-11" />
                  <col />
                  <col className="w-24" />
                  <col className="w-24" />
                </colgroup>
                <thead className="border-hf-border bg-hf-bg sticky top-0 z-10 border-b">
                  <tr>
                    <th className="px-2 py-2 text-left font-medium">
                      <span className="sr-only">Select</span>
                    </th>
                    <th className="px-2 py-2 text-left font-medium">Name</th>
                    <th className="px-2 py-2 text-right font-medium">Targets</th>
                    <th className="px-2 py-2 text-left font-medium">SMILES</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCompounds.map((c) => {
                    const coverage = perCompound[c.compound_id]?.coverage ?? 0;
                    const label = c.canonical_name ?? c.compound_id;
                    return (
                      <tr
                        key={c.compound_id}
                        className={`border-hf-border hover:bg-hf-surface-2 cursor-pointer border-b transition-colors last:border-0 ${
                          selectedCompoundId === c.compound_id ? "bg-hf-surface-2" : ""
                        }`}
                        onClick={() => setSelectedCompoundId(c.compound_id)}
                      >
                        <td className="w-11 px-3 py-2 text-center align-middle">
                          <input
                            type="radio"
                            name="stp-compound"
                            aria-label={`Select ${label}`}
                            checked={selectedCompoundId === c.compound_id}
                            onChange={() => setSelectedCompoundId(c.compound_id)}
                            className="mx-auto block h-4 w-4 cursor-pointer rounded [accent-color:var(--hf-accent)]"
                          />
                        </td>
                        <td className="px-2 py-2 align-middle">
                          <span className="flex min-w-0 items-center gap-1.5">
                            <span className="truncate">{label}</span>
                            {c.source_url && (
                              <SourceIconLink
                                href={c.source_url}
                                label={`Open source for ${label}`}
                                stopPropagation
                              />
                            )}
                          </span>
                        </td>
                        <td className="px-2 py-2 text-right align-middle font-mono text-xs">
                          {coverage}
                        </td>
                        <td className="px-2 py-2 align-middle">
                          {c.smiles ? (
                            <span
                              aria-label={`SMILES available for ${label}`}
                              title="SMILES available"
                              className="text-hf-success inline-flex items-center"
                            >
                              <Check aria-hidden="true" className="size-4" />
                            </span>
                          ) : (
                            <span
                              aria-label={`SMILES missing for ${label}`}
                              title="SMILES missing"
                              className="text-hf-danger inline-flex items-center"
                            >
                              <X aria-hidden="true" className="size-4" />
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {filteredCompounds.length === 0 && (
                <p className="px-3 py-4 text-sm [color:var(--hf-fg-3)]">
                  No compounds match this search.
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!selectedCompoundId}
                onClick={handleCopySmiles}
              >
                <Copy aria-hidden="true" className="size-4" />
                Copy SMILES
              </Button>
              <a
                href={STP_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="border-hf-border-strong bg-hf-bg text-hf-fg-1 hover:bg-hf-surface-2 focus-visible:ring-ring/50 inline-flex h-8 items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors focus-visible:ring-[3px] focus-visible:outline-none"
              >
                <ExternalLink aria-hidden="true" className="size-4" />
                Open SwissTargetPrediction
              </a>
            </div>
            {copyNote && <p className="text-xs [color:var(--hf-fg-3)]">{copyNote}</p>}
          </fieldset>

          <div className="flex min-w-0 flex-col gap-3">
            {/* Threshold + paste-back */}
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
                className="[field-sizing:fixed] h-32 resize-none overflow-y-auto"
              />
            </div>

            {parse.error && pasteText.trim().length > 0 && (
              <p className="text-destructive text-sm" role="alert">
                {parse.error} Expected SwissTargetPrediction columns include <code>Uniprot ID</code>
                , <code>Common name</code>, and <code>Probability*</code>.
              </p>
            )}

            {parsedRows.length > 0 && (
              <p className="text-sm [color:var(--hf-fg-2)]" role="status">
                {parsedTargetLabel}
              </p>
            )}

            <Separator />

            <div className="flex items-center gap-3">
              <StatefulButton
                variant="default"
                disabled={!canImport}
                onClickAsync={async () => {
                  await importMut.mutateAsync().catch(() => undefined);
                }}
              >
                Import
              </StatefulButton>
              {!canImport && !importMut.isPending && (
                <span className="text-sm [color:var(--hf-fg-3)]">Paste a valid CSV to import</span>
              )}
            </div>

            {result && (
              <p className="text-sm" role="status">
                Added {result.added} {result.added === 1 ? "target" : "targets"}.{" "}
                {result.alreadyInRun} {result.alreadyInRun === 1 ? "was" : "were"} already present.{" "}
                {result.failed} could not be matched.
              </p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
