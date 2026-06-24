import { pubchemCompoundUrl, uniprotUrl } from "./externalUrls";

describe("uniprotUrl", () => {
  it("produces the expected UniProt entry URL", () => {
    expect(uniprotUrl("P00533")).toBe("https://www.uniprot.org/uniprotkb/P00533/entry");
  });

  it("percent-encodes special characters in the accession", () => {
    const url = uniprotUrl("foo/bar");
    expect(url).toBe("https://www.uniprot.org/uniprotkb/foo%2Fbar/entry");
  });
});

describe("pubchemCompoundUrl", () => {
  it("produces the expected PubChem compound entry URL", () => {
    expect(pubchemCompoundUrl("969516")).toBe("https://pubchem.ncbi.nlm.nih.gov/compound/969516");
  });

  it("percent-encodes special characters in the CID", () => {
    expect(pubchemCompoundUrl("CID/123")).toBe(
      "https://pubchem.ncbi.nlm.nih.gov/compound/CID%2F123",
    );
  });
});
