import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { SITE_DESCRIPTION } from "../src/lib/pageMeta";

// Collapse all whitespace so prettier's multi-line attribute wrapping does not
// break these single-line substring assertions.
const html = readFileSync(resolve(__dirname, "../index.html"), "utf8").replace(/\s+/g, " ");
const ORIGIN = "https://herbaflow-oscarjiro.vercel.app";

describe("index.html SEO head", () => {
  it("has a meta description matching the one code home", () => {
    expect(html).toContain(`<meta name="description" content="${SITE_DESCRIPTION}"`);
  });
  it("has a canonical link to the prod origin", () => {
    expect(html).toContain(`<link rel="canonical" href="${ORIGIN}/"`);
  });
  it("has Open Graph title/description/url/image", () => {
    expect(html).toContain(`property="og:type" content="website"`);
    expect(html).toContain(`property="og:title" content="Herbaflow"`);
    expect(html).toContain(`property="og:description" content="${SITE_DESCRIPTION}"`);
    expect(html).toContain(`property="og:url" content="${ORIGIN}/"`);
    expect(html).toContain(`property="og:image" content="${ORIGIN}/og.png"`);
    expect(html).toContain(`property="og:image:width" content="1200"`);
    expect(html).toContain(`property="og:image:height" content="630"`);
  });
  it("has a summary_large_image Twitter card", () => {
    expect(html).toContain(`name="twitter:card" content="summary_large_image"`);
    expect(html).toContain(`name="twitter:image" content="${ORIGIN}/og.png"`);
  });
});
