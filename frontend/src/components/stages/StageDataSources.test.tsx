import { render, screen } from "@testing-library/react";
import { StageDataSources } from "./StageDataSources";

it("renders the named sources for the stage", () => {
  render(<StageDataSources stage={3} />);
  expect(screen.getByText(/ChEMBL/)).toBeInTheDocument();
  expect(screen.getByText(/PubChem BioAssay/)).toBeInTheDocument();
  expect(screen.getByText(/UniProt/)).toBeInTheDocument();
});

it("includes UniProt alongside Open Targets for stage 4", () => {
  // Stage 4 resolves disease-target accessions via UniProt (same as Stage 3) — the source list
  // must name it, not just Open Targets (B4-ii).
  render(<StageDataSources stage={4} />);
  expect(screen.getByText(/Open Targets/)).toBeInTheDocument();
  expect(screen.getByText(/UniProt/)).toBeInTheDocument();
});

it("renders nothing for an unknown stage", () => {
  const { container } = render(<StageDataSources stage={9} />);
  expect(container).toBeEmptyDOMElement();
});
