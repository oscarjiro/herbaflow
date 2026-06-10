import { describe, expect, it } from "vitest";
import { parseStpCsv } from "./stp";

const CSV = `Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability,Known actives (3D),Known actives (2D)
p53,Cellular tumor antigen p53,P04637,CHEMBL4096,Transcription factor,0.82,5,12
EGFR,Epidermal growth factor receptor,P00533,CHEMBL203,Kinase,0.40,3,9`;

describe("parseStpCsv", () => {
  it("keys on header names and filters by threshold 0.6", () => {
    const { rows, error } = parseStpCsv(CSV, 0.6);
    expect(error).toBeUndefined();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      uniprot: "P04637",
      common_name: "Cellular tumor antigen p53",
      probability: 0.82,
    });
  });

  it("reports a parse error when a required column is missing", () => {
    const { error } = parseStpCsv("Target,Probability\np53,0.9", 0.6);
    expect(error).toMatch(/Uniprot ID/);
  });

  it("default threshold is 0.6", () => {
    const { rows } = parseStpCsv(CSV);
    expect(rows).toHaveLength(1);
  });

  it("parses a real SwissTargetPrediction export (quoted header, 'Probability*')", () => {
    // Exact header shape exported by SwissTargetPrediction: quoted fields, the
    // probability column carries a trailing asterisk footnote ("Probability*").
    const REAL = `"Target","Common name","Uniprot ID","ChEMBL ID","Target Class","Probability*","Known actives (3D/2D)"
"Cyclin-dependent kinase 2","CDK2","P24941","CHEMBL301","Kinase","0.95","12"
"Carbonic anhydrase 2","CA2","P00918","CHEMBL205","Lyase","0.30","4"`;
    const { rows, error } = parseStpCsv(REAL, 0.6);
    expect(error).toBeUndefined();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      uniprot: "P24941",
      common_name: "CDK2",
      probability: 0.95,
    });
  });
});
