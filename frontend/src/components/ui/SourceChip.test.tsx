import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SourceChip } from "./SourceChip";

describe("SourceChip", () => {
  it("renders the source name as plain text when no url given", () => {
    render(<SourceChip name="PubChem" />);
    expect(screen.getByText("PubChem")).toBeInTheDocument();
  });

  it("does not render a link when no url is provided", () => {
    render(<SourceChip name="KNApSAcK" />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("does not render a link when url is null", () => {
    render(<SourceChip name="KNApSAcK" url={null} />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("renders a link with accessible name when url is given", () => {
    render(<SourceChip name="ChEMBL" url="https://www.ebi.ac.uk/chembl/" />);
    const link = screen.getByRole("link", { name: /chembl/i });
    expect(link).toHaveAttribute("href", "https://www.ebi.ac.uk/chembl/");
  });

  it("link opens in a new tab when url is given", () => {
    render(<SourceChip name="UniProt" url="https://www.uniprot.org" />);
    const link = screen.getByRole("link", { name: /uniprot/i });
    expect(link).toHaveAttribute("target", "_blank");
  });
});
