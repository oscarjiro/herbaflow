# Herbaflow — Design System

> Network‑pharmacology workflow software for herbal medicine discovery.
> Editorial, scientific, restrained. Built for a mixed audience of computational and wet‑lab researchers.

---

## 1. Product context

**What it is.** Herbaflow integrates and automates the currently fragmented network‑pharmacology workflow that researchers use to discover the medicinal potential of herbal plants — with a starting focus on **Indonesian materia medica**. Instead of stitching together a dozen lookup tools, exports and scripts, a user moves through a single continuous, reviewable pipeline.

**The workflow (six steps).**

1. **Plant &amp; disease selection** — pick herbal sources and the target indication.
2. **Compound screening &amp; target prediction** — OB / DL filters, STITCH + SwissTargetPrediction.
3. **Targets overlap** — Venn intersection between disease‑associated and compound‑associated targets.
4. **PPI network construction** — STRING database, confidence ≥ 0.7.
5. **Hub analysis** — degree, betweenness, cluster identification.
6. **Enrichment analysis** — GO / KEGG pathway enrichment, publishable figure.

Headline numbers: **500+ Indonesian plants · 11,000+ metabolites · 10+ curated diseases.**

**What makes it different.**

- **Reviewable, not black‑boxed.** Every step is configurable and inspectable. A scientist can audit and tweak what an automated pipeline would normally hide.
- **Traceable provenance.** Each association in the final network carries its source databases and the parameters that produced it.
- **Built for thesis‑grade rigour.** Currently bounded by static plant/disease/metabolite/target databases; molecular docking is not yet automated. The product makes a virtue of these limits by surfacing them clearly in the UI.

**Audience.** Mixed — technical (bioinformaticians, comp‑bio students) and non‑technical (wet‑lab researchers, faculty, students using it for literature review).

---

## 2. Design principles

1. **Editorial first.** Treat each analysis like a paper, not a dashboard. Big serif headlines, generous margins, narrow measure for body copy.
2. **Restraint over decoration.** One serif, one sans, one accent. Color carries meaning — never mood.
3. **Show the work.** Every chart, network and table is accompanied by the parameters that produced it. Surface filters; never hide them.
4. **Glass as paper.** The glass‑card pattern from the source design is used to layer information panels over the network visualisations — it should always feel like a sheet of vellum, not a Mac OS Big Sur widget.
5. **ASCII as ornament.** The brand has an editorial relationship with the terminal — we use ASCII art (the rotating DNA helix on the landing page; rule lines `————`; bracket framings) as our only ornamental device. No gradients, no fake textures.

---

## 3. File map

```
README.md                  ← this file
SKILL.md                   ← short instruction sheet for using the system
colors_and_type.css        ← all tokens (CSS variables) + @font-face imports
components.css             ← reusable UI primitives (buttons, inputs, cards, …)

assets/
  herbaflow-logo.svg       ← primary lockup (mark + wordmark)
  herbaflow-logo.png       ← raster fallback
  herbaflow-glyph.svg      ← glyph-only mark (favicons, avatars, app icons)
  herbaflow-glyph.png      ← raster fallback
  ascii-dna.js             ← <ascii-dna> web component (background sweep)
  source-*.png             ← original brand sheet & screen references

pages/
  Landing.html             ← marketing / entry page with ASCII DNA hero
  Analysis.html            ← the in‑product workflow screen
  About.html               ← editorial about/thesis page
  Components.html          ← every primitive, in context

previews/                  ← Design‑System‑tab preview cards (one per token group)
index.html                 ← hub: links every page above
```

---

## 4. Content fundamentals

### Voice

- **Plain, declarative, paper‑grade.** “Run analysis.” “Add a target.” “No metabolites matched these filters.” Avoid exclamation marks, marketing verbs (*unlock*, *supercharge*, *seamlessly*), and emoji.
- **Use scientific units and Latin binomials correctly.** *Curcuma longa*, IC₅₀, μmol/L. Italicise binomials in body copy (Instrument Serif italic — true italic, not oblique).
- **First‑person plural is fine** in editorial copy (“We built Herbaflow because…”) but never in product UI (“Your analysis is ready,” not “We’ve finished your analysis”).

### Numbers & data

- Always show the unit. `12.4 μM`, never `12.4`.
- Tabular numerals (`font-variant-numeric: tabular-nums`) for any column of numbers.
- Truncate scientific notation to 3 significant figures by default; expose full precision on hover.

### Microcopy patterns

| Surface | Pattern | Example |
|---|---|---|
| Page title | Serif, sentence case, no period | *Cluster analysis* |
| Section eyebrow | Sans, uppercase, tracked +0.12em | `STEP 02 · TARGETS` |
| Empty state | One short sentence + one CTA | *No metabolites match these filters.*  &nbsp;[Reset filters] |
| Loading state | Verb in present continuous, with what's loading | *Fetching targets from STITCH…* |
| Destructive confirm | Name what will be lost | *Delete this analysis and its 14 saved steps?* |

---

## 5. Visual foundations

### Type pairing — TWO options (toggle via Tweaks)

All fonts are loaded from Google Fonts. Each role has a stack that falls back through near-equivalent typefaces.

| | Display | Body / UI | Mono |
|---|---|---|---|
| **Option A — Editorial (default)** | Instrument Serif → Caudex → Playfair Display | Be Vietnam Pro → DM Sans → Inter | Space Mono |
| **Option B — Clinical** | Fraunces → Caudex | IBM Plex Sans → DM Sans | Space Mono |

Both pairings share the same modular type scale (see `colors_and_type.css`).

### Color

A warm, paper‑tinted neutral ramp + ink. **The main design is monochromatic** — italic emphasis, primary actions, focus rings, link underlines, the wordmark's full stop are all ink, not coloured. The brand reads quiet and editorial, never decorated.

**Sage and terracotta are reserved for data‑visualization only** — cluster fills, chart series, the validated-target badge, the selected-row tint in tables, the ASCII helix base letters. Never use them for editorial emphasis, primary buttons, brand marks, or anything outside a chart, table, or status indicator.

Status colors are *muted earth tones* (moss green, ochre, terracotta), never saturated.

### Spacing & radii

- 4‑pt base scale: `4, 8, 12, 16, 24, 32, 48, 64, 96, 128`.
- Radii are conservative: `2, 4, 8` only. Buttons use `2px`. Cards use `8px`. No fully‑rounded pills outside of badges.
- Shadow is rare. We use 1px borders (rgba ink) for separation; shadow only on floating layers (popovers, modals).

### Iconography

- **Style.** Hairline, 1.25 px stroke, 24 px box, rounded line caps. Monoline — no fills, no gradients.
- **Source.** Lucide *outline* with stroke width set to `1.25`. Custom science glyphs (DNA helix, flask, network node) are drawn to match.
- Do **not** mix multiple icon weights or styles on one screen.

### Logo

- The mark is the official `herbaflow` wordmark + leaf glyph, shipped as `assets/herbaflow-logo.png` (with `.svg` source). Use it as an `<img>` via the `.hf-brand` lockup — *never* re‑typeset the wordmark.
- **Primary lockup:** mark + tagline ("Integrated network pharmacology platform") separated by a 1‑px divider — see `.hf-brand` in `components.css`.
- **Minimum clear space:** the height of the "h" on all sides.
- **Minimum size:** 24 px tall on screen, 8 mm in print.
- Don't recolour, distort, italicise, or place over imagery without a backing plate.
- **Glyph-only mark** (`assets/herbaflow-glyph.png` / `.svg`): the leaf/strand mark on its own, no wordmark. Use for **favicons, social/OG avatars, app icons, chat avatars, and any context where the full lockup won't fit.** Wire it up with `.hf-glyph` (or `.hf-glyph--sm` / `--lg` / `--xl`); favicon `<link>` tags are already in every shipped page. **Don't** swap it in where the full lockup fits — the wordmark is the brand, the glyph is a sigil.

---

## 6. ASCII as a system element

ASCII is the one ornamental tool we allow. Three sanctioned uses:

1. **The rotating double helix** — landing hero only, rendered as an **atmospheric background sweep** (diagonal, radial‑masked, very low contrast). It is the dominant visual but it is *behind* the content, not framed as a figure. Use the `<ascii-dna chars="dots">` variant for this case; the default character set is for stand‑alone figures (which we currently don't ship).
2. **Rule lines** — `————` (em‑dash sequence) used between sections instead of horizontal hairlines, in monospace.
3. **Bracket framings** — `[ CLUSTER 02 ]`, `< 14 targets >` for inline metadata where a badge would feel too UI‑ish.

Never write ASCII boxes, ASCII bullets, or ASCII art that mimics imagery a real illustration would do better.

---

## 7. Known limitations

- Static reference databases (plants, diseases, metabolites, targets). The UI flags result counts and last‑indexed dates so users can judge coverage.
- Molecular docking is not yet automated. The “Docking” step shows a deliberate empty state with manual export instructions instead of pretending to run it.
- This is a solo thesis project — the system is scoped to landing, analysis, about, and the in‑product primitives. No auth, billing, or dashboards.
