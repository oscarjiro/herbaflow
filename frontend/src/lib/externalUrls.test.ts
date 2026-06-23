import { pubchemUrl, uniprotUrl, uniprotGeneUrl } from "./externalUrls";

describe("pubchemUrl", () => {
  it("produces the expected PubChem InChIKey query URL", () => {
    expect(pubchemUrl("RYYVLZVUVIJVGH-UHFFFAOYSA-N")).toBe(
      "https://pubchem.ncbi.nlm.nih.gov/#query=RYYVLZVUVIJVGH-UHFFFAOYSA-N",
    );
  });

  it("percent-encodes special characters", () => {
    const url = pubchemUrl("foo bar");
    expect(url).toBe("https://pubchem.ncbi.nlm.nih.gov/#query=foo%20bar");
  });
});

describe("uniprotUrl", () => {
  it("produces the expected UniProt entry URL", () => {
    expect(uniprotUrl("P00533")).toBe("https://www.uniprot.org/uniprotkb/P00533/entry");
  });

  it("percent-encodes special characters in the accession", () => {
    const url = uniprotUrl("foo/bar");
    expect(url).toBe("https://www.uniprot.org/uniprotkb/foo%2Fbar/entry");
  });
});

describe("uniprotGeneUrl", () => {
  it("produces the expected UniProt gene-search URL for a human gene symbol", () => {
    expect(uniprotGeneUrl("EGFR")).toBe(
      "https://www.uniprot.org/uniprotkb?query=gene:EGFR+AND+organism_id:9606",
    );
  });

  it("percent-encodes special characters in the gene symbol", () => {
    const url = uniprotGeneUrl("foo bar");
    expect(url).toBe(
      "https://www.uniprot.org/uniprotkb?query=gene:foo%20bar+AND+organism_id:9606",
    );
  });
});
