import { render, screen } from "@testing-library/react";
import { StageDataSources } from "./StageDataSources";

it("renders the named sources for the stage", () => {
  render(<StageDataSources stage={3} />);
  expect(screen.getByText(/ChEMBL/)).toBeInTheDocument();
  expect(screen.getByText(/PubChem BioAssay/)).toBeInTheDocument();
  expect(screen.getByText(/UniProt/)).toBeInTheDocument();
});

it("renders nothing for an unknown stage", () => {
  const { container } = render(<StageDataSources stage={9} />);
  expect(container).toBeEmptyDOMElement();
});
