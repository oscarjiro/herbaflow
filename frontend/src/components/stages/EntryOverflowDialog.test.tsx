import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ResolvedCompound, ResolvedTarget } from "@/api/types.gen";
import { EntryOverflowDialog } from "./EntryOverflowDialog";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockCompounds: ResolvedCompound[] = [
  {
    compound_id: "c1",
    canonical_key: "RYYVLZVUVIJVGH-UHFFFAOYSA-N",
    canonical_name: "Curcumin",
    validation_status: "ok",
  },
  {
    compound_id: "c2",
    canonical_key: "AAABBBCCC-UHFFFAOYSA-N",
    canonical_name: "Quercetin",
    validation_status: "ok",
  },
  {
    compound_id: "c3",
    canonical_key: "DDDEEEYYY-UHFFFAOYSA-N",
    canonical_name: null,
    validation_status: "ok",
  },
];

const mockTargets: ResolvedTarget[] = [
  {
    target_id: "t1",
    canonical_key: "Epidermal growth factor receptor",
    gene_symbol: "EGFR",
    uniprot_accession: "P00533",
    validation_status: "ok",
  },
  {
    target_id: "t2",
    canonical_key: "Cellular tumor antigen p53",
    gene_symbol: "TP53",
    uniprot_accession: "P04637",
    validation_status: "ok",
  },
];

// ---------------------------------------------------------------------------
// Compound dialog
// ---------------------------------------------------------------------------

describe("EntryOverflowDialog — compounds", () => {
  it("renders compound rows when open", () => {
    render(
      <EntryOverflowDialog
        kind="compounds"
        open={true}
        onOpenChange={() => {}}
        items={mockCompounds}
        onRemove={() => {}}
      />,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Added compounds")).toBeInTheDocument();
    expect(screen.getByText("Curcumin")).toBeInTheDocument();
    expect(screen.getByText("Quercetin")).toBeInTheDocument();
  });

  it("renders InChIKey as an external link to PubChem", () => {
    render(
      <EntryOverflowDialog
        kind="compounds"
        open={true}
        onOpenChange={() => {}}
        items={mockCompounds.slice(0, 1)}
        onRemove={() => {}}
      />,
    );

    const link = screen.getByRole("link", {
      name: /pubchem entry for RYYVLZVUVIJVGH-UHFFFAOYSA-N/i,
    });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute(
      "href",
      "https://pubchem.ncbi.nlm.nih.gov/#query=RYYVLZVUVIJVGH-UHFFFAOYSA-N",
    );
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("filter input narrows compound rows", async () => {
    const user = userEvent.setup();
    render(
      <EntryOverflowDialog
        kind="compounds"
        open={true}
        onOpenChange={() => {}}
        items={mockCompounds}
        onRemove={() => {}}
      />,
    );

    const filterInput = screen.getByRole("textbox", { name: /filter name/i });
    await user.type(filterInput, "Curcumin");

    expect(screen.getByText("Curcumin")).toBeInTheDocument();
    expect(screen.queryByText("Quercetin")).not.toBeInTheDocument();
  });

  it("clicking delete button calls onRemove with the correct id", async () => {
    const onRemove = vi.fn();
    const user = userEvent.setup();
    render(
      <EntryOverflowDialog
        kind="compounds"
        open={true}
        onOpenChange={() => {}}
        items={mockCompounds}
        onRemove={onRemove}
      />,
    );

    const removeBtn = screen.getByRole("button", { name: /remove curcumin/i });
    await user.click(removeBtn);

    expect(onRemove).toHaveBeenCalledWith("c1");
    expect(onRemove).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Target dialog
// ---------------------------------------------------------------------------

describe("EntryOverflowDialog — targets", () => {
  it("renders target rows when open", () => {
    render(
      <EntryOverflowDialog
        kind="targets"
        open={true}
        onOpenChange={() => {}}
        items={mockTargets}
        onRemove={() => {}}
      />,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Added targets")).toBeInTheDocument();
    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.getByText("TP53")).toBeInTheDocument();
  });

  it("renders UniProt accession as an external link", () => {
    render(
      <EntryOverflowDialog
        kind="targets"
        open={true}
        onOpenChange={() => {}}
        items={mockTargets.slice(0, 1)}
        onRemove={() => {}}
      />,
    );

    const link = screen.getByRole("link", { name: /uniprot entry for P00533/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "https://www.uniprot.org/uniprotkb/P00533/entry");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("filter input narrows target rows by gene symbol", async () => {
    const user = userEvent.setup();
    render(
      <EntryOverflowDialog
        kind="targets"
        open={true}
        onOpenChange={() => {}}
        items={mockTargets}
        onRemove={() => {}}
      />,
    );

    const filterInput = screen.getByRole("textbox", { name: /filter gene/i });
    await user.type(filterInput, "EGFR");

    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.queryByText("TP53")).not.toBeInTheDocument();
  });

  it("clicking delete button calls onRemove with the correct id", async () => {
    const onRemove = vi.fn();
    const user = userEvent.setup();
    render(
      <EntryOverflowDialog
        kind="targets"
        open={true}
        onOpenChange={() => {}}
        items={mockTargets}
        onRemove={onRemove}
      />,
    );

    const removeBtn = screen.getByRole("button", { name: /remove EGFR/i });
    await user.click(removeBtn);

    expect(onRemove).toHaveBeenCalledWith("t1");
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("renders protein name column", () => {
    render(
      <EntryOverflowDialog
        kind="targets"
        open={true}
        onOpenChange={() => {}}
        items={mockTargets.slice(0, 1)}
        onRemove={() => {}}
      />,
    );

    expect(screen.getByText("Epidermal growth factor receptor")).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(
      <EntryOverflowDialog
        kind="targets"
        open={false}
        onOpenChange={() => {}}
        items={mockTargets}
        onRemove={() => {}}
      />,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Compound dialog - columns check
// ---------------------------------------------------------------------------

describe("EntryOverflowDialog — compound columns", () => {
  it("renders InChIKey, Name columns and delete button", () => {
    render(
      <EntryOverflowDialog
        kind="compounds"
        open={true}
        onOpenChange={() => {}}
        items={mockCompounds.slice(0, 1)}
        onRemove={() => {}}
      />,
    );

    // Column headers
    expect(screen.getByText("InChIKey")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();

    // Delete button present
    expect(screen.getByRole("button", { name: /remove curcumin/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Within dialog scoping
// ---------------------------------------------------------------------------

describe("EntryOverflowDialog — dialog scoping", () => {
  it("the delete button is within the dialog", () => {
    render(
      <EntryOverflowDialog
        kind="compounds"
        open={true}
        onOpenChange={() => {}}
        items={mockCompounds.slice(0, 1)}
        onRemove={() => {}}
      />,
    );

    const dialog = screen.getByRole("dialog");
    const deleteBtn = within(dialog).getByRole("button", { name: /remove curcumin/i });
    expect(deleteBtn).toBeInTheDocument();
  });
});
