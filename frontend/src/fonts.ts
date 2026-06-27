// Self-hosted web fonts — the one font-loading home.
//
// Fonts are vendored through @fontsource (self-hosted, same-origin) instead of
// the Google Fonts CDN. Benefits: no render-blocking third-party request,
// deterministic and offline-capable, and only the faces the app actually uses.
// The active type system is display = Instrument Serif, body = Be Vietnam Pro,
// mono = Space Mono; the other families the old CDN @import pulled in were never
// referenced and were dropped.
//
// font-display is Fontsource's default `swap`, so text is always visible. The
// metric-matched fallback faces in index.css (--font-*-fallback) absorb the
// swap so it causes no layout shift, and the two most-visible faces are
// preloaded below so they paint on the first frame instead of swapping in.
//
// Each per-weight import (e.g. "400.css") declares one @font-face per Unicode
// subset (latin / latin-ext / vietnamese) with a unicode-range, so the browser
// only downloads the subset a page actually renders.

// Display — Instrument Serif (headings; italic is used for editorial accents).
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";

// Body — Be Vietnam Pro.
import "@fontsource/be-vietnam-pro/300.css";
import "@fontsource/be-vietnam-pro/400.css";
import "@fontsource/be-vietnam-pro/500.css";
import "@fontsource/be-vietnam-pro/600.css";
import "@fontsource/be-vietnam-pro/700.css";

// Mono — Space Mono.
import "@fontsource/space-mono/400.css";
import "@fontsource/space-mono/700.css";

// Preload the two critical faces — body 400 (most text) and display 400
// (headings) — so they are fetched at highest priority and paint on the first
// frame. Vite rewrites these `?url` imports to the hashed asset path at build.
import bodyWoff2 from "@fontsource/be-vietnam-pro/files/be-vietnam-pro-latin-400-normal.woff2?url";
import displayWoff2 from "@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2?url";

for (const href of [bodyWoff2, displayWoff2]) {
  const link = document.createElement("link");
  link.setAttribute("rel", "preload");
  link.setAttribute("as", "font");
  link.setAttribute("type", "font/woff2");
  link.setAttribute("href", href);
  // Fonts are always fetched in CORS mode; the attribute must be present for the
  // preload to match the actual request (even though these are same-origin).
  link.setAttribute("crossorigin", "anonymous");
  document.head.appendChild(link);
}
