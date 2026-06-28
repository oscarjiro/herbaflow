import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExternalLink } from "./ExternalLink";

describe("ExternalLink", () => {
  it("renders an anchor with the given href", () => {
    render(<ExternalLink href="https://example.com">PubChem</ExternalLink>);
    const link = screen.getByRole("link", { name: /pubchem/i });
    expect(link).toHaveAttribute("href", "https://example.com");
  });

  it("opens in a new tab (target=_blank)", () => {
    render(<ExternalLink href="https://example.com">PubChem</ExternalLink>);
    const link = screen.getByRole("link", { name: /pubchem/i });
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("sets rel=noreferrer for security", () => {
    render(<ExternalLink href="https://example.com">PubChem</ExternalLink>);
    const link = screen.getByRole("link", { name: /pubchem/i });
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("renders the children text", () => {
    render(<ExternalLink href="https://example.com">Open Targets</ExternalLink>);
    expect(screen.getByText("Open Targets")).toBeInTheDocument();
  });

  it("uses the label prop as aria-label when provided", () => {
    render(
      <ExternalLink href="https://example.com" label="Open Targets database">
        Open Targets
      </ExternalLink>,
    );
    const link = screen.getByRole("link", { name: "Open Targets database (opens in new tab)" });
    expect(link).toBeInTheDocument();
  });

  it("accessible name includes the children text when no label given", () => {
    render(<ExternalLink href="https://example.com">UniProt</ExternalLink>);
    // The accessible name is computed from the anchor's text content (children + icon's aria-hidden)
    expect(screen.getByRole("link", { name: /uniprot/i })).toBeInTheDocument();
  });
});
