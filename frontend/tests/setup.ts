import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./handlers";
// Configure the generated API client to point at localhost:8000 (where MSW intercepts).
import "../src/lib/api";

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

// jsdom does not implement matchMedia — provide a stub (defaults to no dark preference).
if (typeof window.matchMedia === "undefined") {
  const stub = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
  window.matchMedia = stub;
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
