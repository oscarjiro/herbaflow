import { type ColumnDef } from "@tanstack/react-table";
import { XIcon } from "lucide-react";
import type { ResolvedCompound, ResolvedTarget } from "@/api/types.gen";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { DataTable } from "@/components/ui/DataTable";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { pubchemUrl, uniprotUrl } from "@/lib/externalUrls";

// ---------------------------------------------------------------------------
// EntryOverflowDialog
//
// Shows the full list of manually-added compounds or targets in a filterable,
// sortable DataTable with a per-row delete button.
// Opens when the user clicks "+N more" in RemovableChipList.
// ---------------------------------------------------------------------------

interface BaseProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface CompoundsProps extends BaseProps {
  kind: "compounds";
  items: ResolvedCompound[];
  onRemove: (id: string) => void;
}

interface TargetsProps extends BaseProps {
  kind: "targets";
  items: ResolvedTarget[];
  onRemove: (id: string) => void;
}

type EntryOverflowDialogProps = CompoundsProps | TargetsProps;

// ---------------------------------------------------------------------------
// Compound columns
// ---------------------------------------------------------------------------

function buildCompoundColumns(onRemove: (id: string) => void): ColumnDef<ResolvedCompound>[] {
  return [
    {
      accessorKey: "canonical_key",
      header: "InChIKey",
      meta: { filterable: true },
      cell: ({ row }) => {
        const key = row.original.canonical_key;
        return (
          <ExternalLink href={pubchemUrl(key)} label={`PubChem entry for ${key}`}>
            <span className="font-mono text-xs">{key}</span>
          </ExternalLink>
        );
      },
    },
    {
      accessorKey: "canonical_name",
      header: "Name",
      meta: { filterable: true },
      cell: ({ row }) =>
        row.original.canonical_name ?? <span className="text-hf-fg-4 italic">—</span>,
    },
    {
      id: "delete",
      header: "",
      meta: { className: "w-10" },
      cell: ({ row }) => {
        const id = row.original.compound_id;
        const label = row.original.canonical_name ?? row.original.canonical_key;
        return (
          <button
            type="button"
            aria-label={`Remove ${label}`}
            onClick={() => onRemove(id)}
            className="text-hf-fg-4 hover:text-hf-terracotta grid size-6 place-items-center rounded transition-colors"
          >
            <XIcon className="size-3.5" aria-hidden="true" />
          </button>
        );
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Target columns
// ---------------------------------------------------------------------------

function buildTargetColumns(onRemove: (id: string) => void): ColumnDef<ResolvedTarget>[] {
  return [
    {
      accessorKey: "uniprot_accession",
      header: "Accession",
      meta: { filterable: true },
      cell: ({ row }) => {
        const acc = row.original.uniprot_accession;
        if (!acc) return <span className="text-hf-fg-4 italic">—</span>;
        return (
          <ExternalLink href={uniprotUrl(acc)} label={`UniProt entry for ${acc}`}>
            <span className="font-mono text-xs">{acc}</span>
          </ExternalLink>
        );
      },
    },
    {
      accessorKey: "canonical_key",
      header: "Protein name",
      meta: { filterable: true },
      cell: ({ row }) => <span className="text-hf-fg-1 text-sm">{row.original.canonical_key}</span>,
    },
    {
      accessorKey: "gene_symbol",
      header: "Gene",
      meta: { filterable: true },
      cell: ({ row }) => row.original.gene_symbol ?? <span className="text-hf-fg-4 italic">—</span>,
    },
    {
      id: "delete",
      header: "",
      meta: { className: "w-10" },
      cell: ({ row }) => {
        const id = row.original.target_id;
        const label =
          row.original.gene_symbol ?? row.original.uniprot_accession ?? row.original.canonical_key;
        return (
          <button
            type="button"
            aria-label={`Remove ${label}`}
            onClick={() => onRemove(id)}
            className="text-hf-fg-4 hover:text-hf-terracotta grid size-6 place-items-center rounded transition-colors"
          >
            <XIcon className="size-3.5" aria-hidden="true" />
          </button>
        );
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Dialog component
// ---------------------------------------------------------------------------

export function EntryOverflowDialog(props: EntryOverflowDialogProps) {
  const { open, onOpenChange, kind, onRemove } = props;

  const title = kind === "compounds" ? "Added compounds" : "Added targets";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        {kind === "compounds" ? (
          <DataTable
            columns={buildCompoundColumns(onRemove)}
            data={props.items}
            emptyMessage="No compounds added."
          />
        ) : (
          <DataTable
            columns={buildTargetColumns(onRemove)}
            data={props.items}
            emptyMessage="No targets added."
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
