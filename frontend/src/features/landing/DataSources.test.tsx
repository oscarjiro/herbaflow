import { render, screen } from "@testing-library/react";
import { DataSources } from "./DataSources";

const EXPECTED = [
  ["KNApSAcK", "https://www.knapsackfamily.com/KNApSAcK/"],
  ["ChEMBL", "https://www.ebi.ac.uk/chembl/"],
  ["PubChem BioAssay", "https://pubchem.ncbi.nlm.nih.gov/"],
  ["Open Targets", "https://platform.opentargets.org/"],
  ["STRING", "https://string-db.org/"],
  ["g:Profiler", "https://biit.cs.ut.ee/gprofiler/"],
] as const;

test("DataSources renders all six databases as external links with correct hrefs", () => {
  render(<DataSources />);
  const links = screen.getAllByRole("link");
  expect(links).toHaveLength(6);
  for (const [label, url] of EXPECTED) {
    const link = screen.getByRole("link", { name: label });
    expect(link).toHaveAttribute("href", url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  }
});

test("DataSources renders the eyebrow and the provenance note", () => {
  render(<DataSources />);
  expect(screen.getByText(/Built on public, citable data/i)).toBeInTheDocument();
  expect(
    screen.getByText(/Every record links back to the database it came from\./i),
  ).toBeInTheDocument();
});
