import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./handlers";
// Configure the generated API client to point at localhost:8000 (where MSW intercepts).
import "../src/lib/api";

// Raise the async utility timeout so that findBy* queries survive the slower
// module-transform pass that heavier dependencies (e.g. recharts) introduce.
configure({ asyncUtilTimeout: 4000 });

// In vitest's jsdom environment, globalThis.AbortController is jsdom's own
// implementation. Node's built-in Request (undici, used by hey-api) validates
// that RequestInit.signal is instanceof Node's AbortSignal.
// jsdom's AbortSignal is from a different VM realm → constructor throws.
//
// Fix: wrap globalThis.Request so that a cross-realm AbortSignal in the init
// is silently stripped before the real Request constructor sees it.
// This means TanStack Query's query-cancellation won't propagate in tests,
// which is acceptable (queries complete normally, just can't be aborted).
const OriginalRequest = globalThis.Request;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).Request = class PatchedRequest extends OriginalRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      try {
        // Probe: does Node accept this signal?
        new OriginalRequest(input instanceof Request ? (input as Request).url : String(input), {
          signal: init.signal,
          method: "HEAD",
        });
      } catch {
        // Cross-realm signal: strip it so the real Request doesn't throw.
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { signal: _stripped, ...rest } = init;
        super(input, rest);
        return;
      }
    }
    super(input, init);
  }
};

// jsdom does not implement URL.createObjectURL — provide a no-op stub so that
// components that build CSV blob download links don't crash in tests.
if (typeof URL.createObjectURL === "undefined") {
  URL.createObjectURL = () => "blob:mock";
}
if (typeof URL.revokeObjectURL === "undefined") {
  URL.revokeObjectURL = () => {};
}

// jsdom does not implement the pointer-capture / scrollIntoView APIs that Radix
// primitives (e.g. the shadcn Select) call on open. Stub them so those components
// can be driven in tests without throwing.
if (typeof Element.prototype.hasPointerCapture === "undefined") {
  Element.prototype.hasPointerCapture = () => false;
}
if (typeof Element.prototype.setPointerCapture === "undefined") {
  Element.prototype.setPointerCapture = () => {};
}
if (typeof Element.prototype.releasePointerCapture === "undefined") {
  Element.prototype.releasePointerCapture = () => {};
}
if (typeof Element.prototype.scrollIntoView === "undefined") {
  Element.prototype.scrollIntoView = () => {};
}

// jsdom does not implement matchMedia. Provide a controllable stub: defaults to no dark
// preference, supports addEventListener("change") so the theme provider's live OS tracking
// is testable. Tests can flip the preference via __setMatchMediaDark(boolean).
if (typeof window.matchMedia === "undefined") {
  const listeners = new Set<(e: MediaQueryListEvent) => void>();
  let prefersDark = false;
  const mql = {
    get matches() {
      return prefersDark;
    },
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => listeners.add(cb),
    removeEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => listeners.delete(cb),
    addListener: (cb: (e: MediaQueryListEvent) => void) => listeners.add(cb),
    removeListener: (cb: (e: MediaQueryListEvent) => void) => listeners.delete(cb),
    dispatchEvent: () => false,
  };
  window.matchMedia = (() => mql as unknown as MediaQueryList) as typeof window.matchMedia;
  (globalThis as unknown as { __setMatchMediaDark: (v: boolean) => void }).__setMatchMediaDark = (
    v: boolean,
  ) => {
    prefersDark = v;
    listeners.forEach((cb) => cb({ matches: v } as MediaQueryListEvent));
  };
}

// jsdom does not implement ResizeObserver — Radix Popover uses it internally.
// Provide a no-op stub so popovers/comboboxes can open in tests.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
