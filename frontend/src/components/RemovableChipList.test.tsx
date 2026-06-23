import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ResolvedCompound, ResolvedTarget } from "@/api/types.gen";
import { RemovableChipList } from "./RemovableChipList";

test("renders hf-token chips and removes on click", async () => {
  const onRemove = vi.fn();
  const { container } = render(
    <RemovableChipList
      items={[{ id: "x", name: "CURCUMIN" }]}
      getKey={(i) => i.id}
      getLabel={(i) => i.name}
      onRemove={onRemove}
      ariaLabel="compounds"
    />,
  );
  // Classes live on the <span> inside <li>
  const chip = container.querySelector("li span")!;
  expect(chip.className).toMatch(/font-mono/);
  expect(chip.className).toMatch(/border-hf-border-strong/);
  expect(chip.className).not.toMatch(/bg-accent\b/);
  await userEvent.click(screen.getByRole("button"));
  expect(onRemove).toHaveBeenCalled();
});

// ---------------------------------------------------------------------------
// Overflow affordance — compounds
// ---------------------------------------------------------------------------

function makeCompounds(n: number): ResolvedCompound[] {
  return Array.from({ length: n }, (_, i) => ({
    compound_id: `c${i}`,
    canonical_key: `INCHIKEY${i}-UHFFFAOYSA-N`,
    canonical_name: `Compound ${i}`,
    validation_status: "ok",
  }));
}

function makeTargets(n: number): ResolvedTarget[] {
  return Array.from({ length: n }, (_, i) => ({
    target_id: `t${i}`,
    canonical_key: `Protein ${i}`,
    gene_symbol: `GENE${i}`,
    uniprot_accession: `P0000${i}`,
    validation_status: "ok",
  }));
}

test("shows all chips when count is at the limit (10)", () => {
  const items = makeCompounds(10);
  render(
    <RemovableChipList
      overflowKind="compounds"
      items={items}
      getKey={(r) => r.compound_id}
      getLabel={(r) => r.canonical_name ?? r.compound_id}
      onRemove={() => {}}
      ariaLabel="Added compounds"
    />,
  );

  // All 10 chips + no overflow button
  expect(screen.queryByRole("button", { name: /show all/i })).not.toBeInTheDocument();
  for (let i = 0; i < 10; i++) {
    expect(screen.getByText(`Compound ${i}`)).toBeInTheDocument();
  }
});

test("shows +N more button when count exceeds 10", () => {
  const items = makeCompounds(13);
  render(
    <RemovableChipList
      overflowKind="compounds"
      items={items}
      getKey={(r) => r.compound_id}
      getLabel={(r) => r.canonical_name ?? r.compound_id}
      onRemove={() => {}}
      ariaLabel="Added compounds"
    />,
  );

  // First 10 visible
  expect(screen.getByText("Compound 0")).toBeInTheDocument();
  expect(screen.queryByText("Compound 10")).not.toBeInTheDocument();

  // Overflow button shows correct hidden count
  const overflowBtn = screen.getByRole("button", { name: /show all 13 items/i });
  expect(overflowBtn).toBeInTheDocument();
  expect(overflowBtn).toHaveTextContent("+3 more");
});

test("clicking +N more opens the overflow dialog", async () => {
  const user = userEvent.setup();
  const items = makeCompounds(12);
  render(
    <RemovableChipList
      overflowKind="compounds"
      items={items}
      getKey={(r) => r.compound_id}
      getLabel={(r) => r.canonical_name ?? r.compound_id}
      onRemove={() => {}}
      ariaLabel="Added compounds"
    />,
  );

  const overflowBtn = screen.getByRole("button", { name: /show all 12 items/i });
  await user.click(overflowBtn);

  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(screen.getByText("Added compounds")).toBeInTheDocument();
  // The DataTable shows 10/page; verify all 12 are present via the pager read-out.
  // "Showing 1–10 of 12" means the dialog received all 12 items.
  expect(screen.getByText(/of 12/)).toBeInTheDocument();
});

test("delete via overflow dialog calls the existing onRemove handler", async () => {
  const user = userEvent.setup();
  const onRemove = vi.fn();
  const items = makeTargets(12);
  render(
    <RemovableChipList
      overflowKind="targets"
      items={items}
      getKey={(t) => t.target_id}
      getLabel={(t) => t.gene_symbol ?? t.target_id}
      onRemove={onRemove}
      ariaLabel="Added targets"
    />,
  );

  await user.click(screen.getByRole("button", { name: /show all 12 items/i }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();

  // Delete the first target (GENE0) via the dialog
  const removeBtn = screen.getByRole("button", { name: /remove GENE0/i });
  await user.click(removeBtn);

  // The existing onRemove is called with the full target object (not just id)
  expect(onRemove).toHaveBeenCalledTimes(1);
  expect(onRemove).toHaveBeenCalledWith(items[0]);
});

test("no overflow button without overflowKind even with >10 items", () => {
  const items = Array.from({ length: 15 }, (_, i) => ({ id: `x${i}`, name: `Item ${i}` }));
  render(
    <RemovableChipList
      items={items}
      getKey={(i) => i.id}
      getLabel={(i) => i.name}
      onRemove={() => {}}
      ariaLabel="Items"
    />,
  );

  // All 15 items rendered (no overflow limit applied when overflowKind is absent)
  expect(screen.queryByRole("button", { name: /show all/i })).not.toBeInTheDocument();
  expect(screen.getByText("Item 14")).toBeInTheDocument();
});
