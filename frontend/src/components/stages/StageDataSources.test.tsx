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

it("shows only PubChem for a user-provided Stage 1 (manual compounds)", () => {
  render(<StageDataSources stage={1} userProvided />);
  expect(screen.getByText(/PubChem/)).toBeInTheDocument();
  expect(screen.queryByText(/KNApSAcK/)).not.toBeInTheDocument();
});

it("shows only UniProt for a user-provided Stage 3 / Stage 4", () => {
  const { rerender } = render(<StageDataSources stage={3} userProvided />);
  expect(screen.getByText(/UniProt/)).toBeInTheDocument();
  expect(screen.queryByText(/ChEMBL/)).not.toBeInTheDocument();
  rerender(<StageDataSources stage={4} userProvided />);
  expect(screen.getByText(/UniProt/)).toBeInTheDocument();
  expect(screen.queryByText(/Open Targets/)).not.toBeInTheDocument();
});

it("shows the computed sources when not user-provided", () => {
  render(<StageDataSources stage={3} />);
  expect(screen.getByText(/ChEMBL/)).toBeInTheDocument();
});

it("renders a linked source name when url present", () => {
  render(<StageDataSources stage={3} userProvided={false} />);
  const link = screen.getByRole("link", { name: "ChEMBL" });
  expect(link).toHaveAttribute("href", "https://www.ebi.ac.uk/chembl/");
});

it("renders a plain name when url is null", () => {
  render(<StageDataSources stage={5} userProvided={false} />);
  expect(screen.getByText(/Set intersection/)).toBeInTheDocument();
});
