# Herbaflow Design System — Quick Reference

A solo‑thesis network‑pharmacology tool. Editorial scientific feel. Read `README.md` first for the full system rationale; this file is for fast lookups while building.

## Loading the system

```html
<link rel="stylesheet" href="colors_and_type.css" />
<link rel="stylesheet" href="components.css" />
<!-- Optional, only on landing -->
<script src="assets/ascii-dna.js" defer></script>
```

All tokens are CSS custom properties on `:root` — never inline a hex or px value that exists as a token.

## Type pairing toggle

Refer to the Type row in Core Tokens and `README.md`.

```html
<html data-type-pair="clinical"></html>
```

## Core tokens (cheat sheet)

| Group    | Token                                                              | Use                                                                                                                   |
| -------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| BG       | `--hf-bg`, `--hf-surface`, `--hf-surface-2`                        | page → card → nested                                                                                                  |
| FG       | `--hf-fg-1` / `-2` / `-3` / `-4`                                   | primary → metadata → disabled                                                                                         |
| Border   | `--hf-border`, `--hf-border-strong`                                | hairlines, focused inputs                                                                                             |
| Viz-only | `--hf-sage`, `--hf-sage-soft`, `--hf-sage-faint`, `--hf-sage-deep` | data-viz accent (clusters, charts, validated badge) — NOT brand                                                       |
| Viz-only | `--hf-terracotta`, `--hf-terracotta-soft`                          | secondary data-viz accent                                                                                             |
| Status   | `--hf-success`, `--hf-warning`, `--hf-danger`                      | muted earth tones                                                                                                     |
| Type     | `--font-display`, `--font-sans`, `--font-mono`                     | Instrument Serif / Be Vietnam Pro / Space Mono (Google Fonts — fallbacks: Caudex → Playfair Display; DM Sans → Inter) |
| Scale    | `--text-xs` … `--text-display`                                     | 12 → 64px                                                                                                             |
| Space    | `--space-1` … `--space-12`                                         | 4 → 128px (4pt base)                                                                                                  |
| Radius   | `--radius-1` / `-2` / `-3`                                         | 2 / 4 / 8                                                                                                             |

## Components (in `components.css`)

`.hf-btn` (`.hf-btn--primary`, `--secondary`, `--ghost`, `--sm`, `--lg`) ·
`.hf-input` · `.hf-select` · `.hf-checkbox` · `.hf-toggle` ·
`.hf-card` (`.hf-card--glass`) ·
`.hf-eyebrow` · `.hf-rule` · `.hf-badge` ·
`.hf-table` · `.hf-chart` · `.hf-legend` ·
`.hf-nav`, `.hf-sidebar` ·
`.hf-modal`, `.hf-toast` ·
`.hf-empty`, `.hf-loading`

## Assets

- `assets/herbaflow-logo.png` / `.svg` — primary lockup (mark + wordmark). Use via `.hf-brand`.
- `assets/herbaflow-glyph.png` / `.svg` — glyph-only mark. Use via `.hf-glyph` for favicons, avatars, app icons, dense UI affordances. Already wired as favicon on every shipped page.
- `assets/ascii-dna.js` — `<ascii-dna>` web component. `chars="dots"` for atmospheric backgrounds.

## Do / don't

✅ One serif heading per section. Tabular nums in tables. Italic for _binomials_ (color: inherit, not sage). One ink-filled primary action per screen.
❌ No gradients, no emoji, no shadows for cards, no fully-rounded pills (except `.hf-badge--pill`), no saturated reds/blues. **No sage outside data-viz contexts.** ASCII ornament only via `<ascii-dna>`, `.hf-rule` and `[ bracketed metadata ]`.
