import { uniprotUrl } from "./externalUrls";

describe("uniprotUrl", () => {
  it("produces the expected UniProt entry URL", () => {
    expect(uniprotUrl("P00533")).toBe("https://www.uniprot.org/uniprotkb/P00533/entry");
  });

  it("percent-encodes special characters in the accession", () => {
    const url = uniprotUrl("foo/bar");
    expect(url).toBe("https://www.uniprot.org/uniprotkb/foo%2Fbar/entry");
  });
});
