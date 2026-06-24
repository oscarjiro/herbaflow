import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { listPlantsOptions } from "../../api/@tanstack/react-query.gen";
import type { AnalysisRead, PlantRead, ResolvedCompound } from "../../api/types.gen";
import { MAX_COMPOUNDS } from "../../contract";
import { useAddWithDedup } from "../../hooks/useAddWithDedup";
import { useStageEntityEdit } from "../../hooks/useStageEntityEdit";
import { atMinEntities, isUserRemoved } from "../../lib/entities";
import { pubchemCompoundUrl } from "../../lib/externalUrls";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataTable } from "@/components/ui/DataTable";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { ExpandableListCell } from "@/components/ui/ExpandableListCell";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { CompoundValidateBox } from "../CompoundValidateBox";
import { AlreadyInRunNote } from "./AlreadyInRunNote";
import { EntityAddControl } from "./EntityAddControl";
import { StageDataSources } from "./StageDataSources";
import { StageEntityContext } from "./StageEntityContext";
import { StageSummaryCard } from "./StageSummaryCard";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Full compound shape emitted by stage1.run — includes structure fields not
 * carried through the edit-layer minimal row (which only keeps compound_id /
 * canonical_name / tag after a set-edit re-derive).
 */
type Stage1Compound = {
  compound_id: string;
  canonical_name?: string | null;
  inchikey?: string | null;
  smiles?: string | null;
  pubchem_cid?: string | null;
  source_url?: string | null;
  tag?: string;
};

type Stage1Data = {
  count?: number;
  compounds?: Stage1Compound[];
  per_plant?: Record<string, string[]>;
  state?: string;
};

type Stage1Row = {
  id: string;
  label: string;
  inchikey: string | null;
  smiles: string | null;
  pubchem_cid: string | null;
  source_url: string | null;
  plantNames: string[];
  tag?: string;
};

// ---------------------------------------------------------------------------
// CSV builder (inline — raw values, no formatSig)
// ---------------------------------------------------------------------------

const CSV_HEADER = "inchikey,name,smiles,plant_sources,source_url";

function buildCsvRows(rows: Stage1Row[], showPlantSources: boolean): unknown[][] {
  return rows.map((r) => [
    r.inchikey ?? null,
    r.label,
    r.smiles ?? null,
    showPlantSources ? r.plantNames.join(";") : "",
    r.source_url ?? null,
  ]);
}

// ---------------------------------------------------------------------------
// Plant-catalog resolution helpers (limit mirrors useEntitySubjects)
// ---------------------------------------------------------------------------

const CATALOG_LIMIT = 1000;

/**
 * Invert the stage-1 per_plant map to a per-compound lookup.
 * per_plant = { plant_id: [compound_id, ...] }
 * Returns Map<compound_id, plant_id[]>
 */
function invertPerPlant(perPlant: Record<string, string[]> | undefined): Map<string, string[]> {
  const map = new Map<string, string[]>();
  if (!perPlant) return map;
  for (const [plantId, compoundIds] of Object.entries(perPlant)) {
    for (const cid of compoundIds) {
      const list = map.get(cid) ?? [];
      list.push(plantId);
      map.set(cid, list);
    }
  }
  return map;
}

function buildPlantNamesMap(plants: PlantRead[] | undefined): Map<string, string> {
  const byId = new Map<string, string>();
  for (const p of plants ?? []) {
    byId.set(p.plant_id, p.canonical_scientific_name ?? p.plant_id);
  }
  return byId;
}

// ---------------------------------------------------------------------------
// Stage1View
// ---------------------------------------------------------------------------

export function Stage1View({ data }: { data: AnalysisRead }) {
  const stage1 = (data.stage_results?.["1"] ?? {}) as Stage1Data;
  const analysisId = data.analysis_id;
  const stageState = (data as { stage_state?: Record<string, string> }).stage_state?.["1"];

  const params = data.parameters as Record<string, unknown> | undefined;
  const inputModes = params?.input_modes as { plant?: string; disease?: string } | undefined;
  const labels = params?.labels as { plant?: string; disease?: string } | undefined;
  const plantIds = params?.plant_ids as string[] | undefined;

  // Show the plant-source column only in multi-plant selection mode.
  const isSelectionMode = !inputModes || inputModes.plant === "selection";
  const isMultiPlant = isSelectionMode && (plantIds?.length ?? 0) > 1;

  // Fetch the plant catalog (deduped by TanStack Query; only needed for the column).
  const { data: plantsData } = useQuery(listPlantsOptions({ query: { limit: CATALOG_LIMIT } }));

  const edit = useStageEntityEdit({
    analysisId,
    stage: 1,
    entity: { singular: "compound", plural: "compounds" },
  });

  const currentCompoundIds = new Set((stage1.compounds ?? []).map((c) => c.compound_id));
  const { alreadyInRun, handleAdd } = useAddWithDedup<ResolvedCompound>({
    currentIds: currentCompoundIds,
    getId: (r) => r.compound_id,
    onAddIds: (ids) => edit.mutate({ add: ids, remove: [] }),
  });

  // Derived rows (hide user-removed).
  const plantNamesById = useMemo(() => buildPlantNamesMap(plantsData), [plantsData]);
  const compoundToPlants = useMemo(() => invertPerPlant(stage1.per_plant), [stage1.per_plant]);

  const compounds = stage1.compounds ?? [];
  const current = stage1.count ?? compounds.filter((c) => c.tag !== "user-removed").length;
  const totalPlants = isSelectionMode
    ? (plantIds?.length ?? Object.keys(stage1.per_plant ?? {}).length)
    : labels?.plant && labels.plant !== "N/A"
      ? 1
      : 0;
  const atMin = atMinEntities(current);

  const rows: Stage1Row[] = useMemo(
    () =>
      compounds
        .filter((c) => !isUserRemoved(c.tag))
        .map((c) => {
          const plantIds = compoundToPlants.get(c.compound_id) ?? [];
          return {
            id: c.compound_id,
            label: c.canonical_name ?? c.compound_id,
            inchikey: c.inchikey ?? null,
            smiles: c.smiles ?? null,
            pubchem_cid: c.pubchem_cid ?? null,
            source_url: c.source_url ?? null,
            plantNames: plantIds.map((pid) => plantNamesById.get(pid) ?? pid),
            tag: c.tag,
          };
        }),
    [compounds, compoundToPlants, plantNamesById],
  );

  const csvRows = useMemo(() => buildCsvRows(rows, isMultiPlant), [rows, isMultiPlant]);

  function handleRemove(id: string) {
    edit.mutate({ add: [], remove: [id] });
  }

  if (stageState === "not_applicable") {
    return (
      <section className="stage-view stage-view--na" aria-disabled>
        <h2>Step 1: Compounds</h2>
        <p className={cn("text-sm", "[color:var(--hf-fg-3)]")}>Not applicable for this run.</p>
      </section>
    );
  }

  const isUserProvided = stageState === "user_provided";

  // ---------------------------------------------------------------------------
  // Column definitions
  // ---------------------------------------------------------------------------

  const columns: ColumnDef<Stage1Row>[] = [
    {
      id: "inchikey",
      header: "InChIKey",
      cell: ({ row }) => {
        const r = row.original;
        if (!r.inchikey) return <span className="text-hf-fg-3">—</span>;
        if (r.source_url) {
          return (
            <ExternalLink href={r.source_url} className="font-mono text-xs">
              {r.inchikey}
            </ExternalLink>
          );
        }
        return <span className="font-mono text-xs">{r.inchikey}</span>;
      },
    },
    {
      id: "name",
      header: "Name",
      cell: ({ row }) =>
        row.original.pubchem_cid ? (
          <ExternalLink href={pubchemCompoundUrl(row.original.pubchem_cid)}>
            {row.original.label}
          </ExternalLink>
        ) : (
          <span>{row.original.label}</span>
        ),
    },
    {
      id: "smiles",
      header: "SMILES",
      cell: ({ row }) => {
        const s = row.original.smiles;
        if (!s) return <span className="text-hf-fg-3">—</span>;
        return <span className="font-mono text-xs break-all">{s}</span>;
      },
    },
    // Plant-source column — rendered only in multi-plant selection mode.
    ...(isMultiPlant
      ? ([
          {
            id: "plant_sources",
            header: "Plant source(s)",
            enableSorting: false,
            cell: ({ row }) => <ExpandableListCell items={row.original.plantNames} />,
          },
        ] as ColumnDef<Stage1Row>[])
      : []),
    {
      id: "actions",
      header: "",
      enableSorting: false,
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`Remove ${row.original.label}`}
          onClick={() => handleRemove(row.original.id)}
          disabled={atMin}
          title={atMin ? "A stage must keep at least one entry." : undefined}
        >
          ✕
        </Button>
      ),
    },
  ];

  return (
    <section className="flex flex-col gap-4">
      {/* Context + sources */}
      <div className="flex flex-col gap-1">
        <StageEntityContext data={data} side="plant" />
        <StageDataSources stage={1} userProvided={isUserProvided} />
      </div>

      {isUserProvided && (
        <div>
          <Badge variant="secondary">Provided by you</Badge>
        </div>
      )}

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <StageSummaryCard
          value={current}
          label="Total compounds"
          ariaLabel={`${current} total compounds`}
        />
        <StageSummaryCard
          value={totalPlants}
          label="Selected plants"
          ariaLabel={`${totalPlants} selected plants`}
          muted
        />
      </div>

      {/* Compound list card */}
      <Card>
        <CardHeader className="pb-0">
          <div className="flex flex-wrap items-center gap-3">
            <CsvDownloadButton
              header={CSV_HEADER}
              rows={csvRows}
              filename="compounds.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pt-3">
          <div className="table-wrapper">
            <DataTable columns={columns} data={rows} emptyMessage="No compounds yet." />
          </div>
          <EntityAddControl current={current} cap={MAX_COMPOUNDS}>
            <CompoundValidateBox label="Add compounds" onResolved={handleAdd} showAddButton />
          </EntityAddControl>
          <AlreadyInRunNote
            labels={alreadyInRun.map((c) => c.canonical_name ?? c.canonical_key ?? c.compound_id)}
          />
        </CardContent>
      </Card>
    </section>
  );
}
