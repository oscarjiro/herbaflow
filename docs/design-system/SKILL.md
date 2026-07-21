# Herbaflow Design System — Quick Reference

A solo-thesis network-pharmacology tool. Editorial scientific feel. Read `README.md` first for the
full system rationale; this file is for fast lookups while building.

> [!IMPORTANT]
> **This is a reference, not the stylesheet the app loads.** The application is Tailwind v4 and
> defines its live tokens in [`frontend/src/index.css`](../../frontend/src/index.css). The two CSS
> files here exist so the mockups in `pages/` render standalone, and so the token values have a
> documented home. If they ever disagree with the frontend, the frontend is right.
>
> This system covers **visual style only**. It is never a source for the science or the pipeline.

## Using it

**In the app:** use the `hf-*` tokens through Tailwind. Never hardcode a hex or px value that exists
as a token.

**In these mockups:** link both stylesheets.

```html
<link rel="stylesheet" href="colors_and_type.css" />
<link rel="stylesheet" href="components.css" />
<!-- Optional, only on landing -->
<script src="assets/ascii-dna.js" defer></script>
```

## The one rule that bites

In the frontend, **every component recipe in `index.css` must live inside `@layer components`.**
Tailwind orders its `utilities` layer after `components`, so a recipe written outside a layer
outranks utility classes and silently breaks every override at the call site. This applies to the
glass recipe too. See `frontend/CLAUDE.md`.

## Theming

Themes switch on a **class on `<html>`**, not a media query, so the user's choice beats the OS
setting.

```html
<html class="dark"></html>
```

In the app this is declared as a Tailwind v4 custom variant:

```css
@custom-variant dark (&:where(.dark, .dark *));
```

Only tokens whose value changes are re-declared under `.dark`: surfaces, foregrounds, borders,
data-viz accents, status colours, and glass. Type, spacing, radii, and motion are theme-independent.

Dark is **not an inversion**. The neutrals stay warm, and the accents lift in lightness so they hold
contrast against a dark ground instead of going muddy.

Anything reading a token at runtime (charts, canvas) must re-read on theme change rather than
caching the value once. The frontend does this with a `MutationObserver` on `<html>`.

## Type pairing toggle

Refer to the Type row in Core Tokens and `README.md`.

```html
<html data-type-pair="clinical"></html>
```

## Core tokens (cheat sheet)

| Group    | Token                                                              | Use                                                                                                                   |
| -------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| BG       | `--hf-bg`, `--hf-surface`, `--hf-surface-2`, `--hf-bg-raised`      | page → card → nested → raised wash                                                                                    |
| FG       | `--hf-fg-1` / `-2` / `-3` / `-4`                                   | primary → metadata → disabled                                                                                         |
| Accent   | `--hf-accent`                                                      | alias: ink in light, paper in dark. The UI reads monochrome                                                            |
| Border   | `--hf-border`, `--hf-border-strong`, `--hf-dot`                    | hairlines, emphasis, dotted grids and separator dots                                                                  |
| Viz-only | `--hf-sage`, `--hf-sage-soft`, `--hf-sage-faint`, `--hf-sage-deep` | data-viz accent (clusters, charts, validated badge) — NOT brand                                                       |
| Viz-only | `--hf-terracotta`, `--hf-terracotta-soft`                          | secondary data-viz accent                                                                                             |
| Status   | `--hf-success`, `--hf-warning`, `--hf-danger`, `--hf-info`         | muted earth tones                                                                                                     |
| Control  | `--hf-switch-track-off`                                            | switch track, off state                                                                                               |
| Glass    | see the Glass section below                                        | tint + shine, layered over a backdrop filter                                                                          |
| Type     | `--font-display`, `--font-sans`, `--font-mono`                     | Instrument Serif / Be Vietnam Pro / Space Mono (Google Fonts — fallbacks: Caudex → Playfair Display; DM Sans → Inter) |
| Scale    | `--text-xs` … `--text-display`                                     | 12 → 64px                                                                                                             |
| Space    | `--space-1` … `--space-12`                                         | 4 → 128px (4pt base)                                                                                                  |
| Radius   | `--radius-1` / `-2` / `-3`                                         | 2 / 4 / 8                                                                                                             |

## Glass

Glass is built from a **tint** plus a **shine** over a backdrop filter, not from one flat
translucent fill.

| Token                          | Role                                                       |
| ------------------------------ | ---------------------------------------------------------- |
| `--hf-glass-tint`              | body wash                                                  |
| `--hf-glass-tint-strong`       | heavier wash for denser chrome                             |
| `--hf-glass-tint-clear`        | lighter wash where content must stay legible through it    |
| `--hf-glass-tint-clear-strong` | as above, heavier                                          |
| `--hf-glass-shine`             | specular edge                                              |
| `--hf-glass-shine-2`           | secondary specular edge                                    |
| `--hf-glass-shadow`            | floating-layer shadow                                      |

Tiers, applied as classes: `.hf-glass` (base) with `--chrome`, `--icon`, `--overlay`, `--raised`,
plus `.hf-glass-panel` for full panels. Content inside a glass surface goes in `.hf-glass__content`
so it sits above the tint and shine layers.

Real refraction is Chromium-only and is feature-detected at runtime; other browsers fall back to a
frosted treatment. Do not assume refraction is present.

`--hf-glass-bg-strong` and `--hf-glass-border` are **legacy** flat fills, kept only because the older
mockup pages still reference them. Do not use them in new work.

## Components (in `components.css`)

`.hf-btn` (`--primary`, `--secondary`, `--ghost`, `--danger`, `--warning`, `--sage`, `--sm`, `--lg`, `--icon`) ·
`.hf-input` · `.hf-select` · `.hf-textarea` · `.hf-checkbox` · `.hf-radio` · `.hf-toggle` · `.hf-slider` ·
`.hf-card` (`--glass`, `--bordered`, `--flat`) ·
`.hf-badge` (`--pill`, `--outline`, `--sage`, `--terra`, `--success`, `--warning`, `--danger`, `--info`) ·
`.hf-table` · `.hf-chart` · `.hf-legend` · `.hf-progress` · `.hf-steps` ·
`.hf-nav` · `.hf-sidebar` · `.hf-modal` · `.hf-toast` · `.hf-empty` · `.hf-loading`

## Editorial primitives

`.hf-eyebrow` (uppercase tracked label) · `.hf-rule` (em-dash rule line) · `.hf-bracket`
(`[ bracketed metadata ]`) · `.hf-binomial` (italic serif for Latin names) · `.hf-link` (underline
with ink-on-hover) · `.hf-num` (tabular numerals) · `.hf-ink-focus` (shared focus ring).

## App-only classes

Live in `frontend/src/index.css`, not in `components.css`, because they depend on the running app:

- `.hf-bg` with `.hf-bg__glow--g1/--g2/--g3` and `.hf-bg__grain` — the ambient page background.
- `.hf-anim-fade`, `.hf-anim-slide-left`, `.hf-anim-slide-right` — route and panel transitions.
- `.hf-dna` — the landing ASCII helix host.
- `.hf-ai-orb` — the processing indicator.
- `.hf-burger` — the mobile nav trigger.

## Assets

- `assets/herbaflow-logo.png` / `.svg` — primary lockup (mark + wordmark). Use via `.hf-brand`.
- `assets/herbaflow-glyph.png` / `.svg` — glyph-only mark. Use via `.hf-glyph` for favicons, avatars, app icons, dense UI affordances. Already wired as favicon on every shipped page.
- `assets/ascii-dna.js` — `<ascii-dna>` web component. `chars="dots"` for atmospheric backgrounds.

## Do / don't

✅ One serif heading per section. Tabular nums in tables. Italic for _binomials_ (color: inherit, not sage). One ink-filled primary action per screen. Style both themes.
❌ No gradients, no emoji, no shadows for cards, no fully-rounded pills (except `.hf-badge--pill`), no saturated reds/blues. **No sage outside data-viz contexts.** ASCII ornament only via `<ascii-dna>`, `.hf-rule` and `[ bracketed metadata ]`.
