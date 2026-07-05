import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const read = (p: string) => readFileSync(resolve(__dirname, "../public", p), "utf8");
const ORIGIN = "https://herbaflow-oscarjiro.vercel.app";

describe("robots.txt", () => {
  const txt = read("robots.txt");
  it("allows all and points at the sitemap", () => {
    expect(txt).toContain("User-agent: *");
    expect(txt).toContain("Allow: /");
    expect(txt).toContain(`Sitemap: ${ORIGIN}/sitemap.xml`);
  });
});

describe("sitemap.xml", () => {
  const xml = read("sitemap.xml");
  it("lists the public routes and omits app routes", () => {
    expect(xml).toContain(`<loc>${ORIGIN}/</loc>`);
    expect(xml).toContain(`<loc>${ORIGIN}/about</loc>`);
    expect(xml).not.toContain("/analysis");
  });
});
