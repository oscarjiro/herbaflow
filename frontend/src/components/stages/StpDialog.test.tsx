import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { StpDialog } from "./StpDialog";

const COMPOUNDS = [
  { compound_id: "C1", canonical_name: "Quercetin", smiles: "OC1=CC=CC=C1" },
  { compound_id: "C2", canonical_name: "Curcumin", smiles: null },
];

const PER_COMPOUND = {
  C1: { coverage: 0 },
  C2: { coverage: 0.5 },
};

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("StpDialog — D10: disabled Import reason hint", () => {
  it("shows a 'paste a valid CSV to import' hint when no rows are parsed (import disabled)", () => {
    wrap(
      <StpDialog
        compounds={COMPOUNDS}
        perCompound={PER_COMPOUND}
        existingTargetIds={[]}
        onAddTargets={() => {}}
      />,
    );

    // Import button should be disabled
    const importBtn = screen.getByRole("button", { name: /import/i });
    expect(importBtn).toBeDisabled();

    // A reason hint must be present when import is disabled
    expect(screen.getByText(/paste a valid csv to import/i)).toBeInTheDocument();
  });
});
