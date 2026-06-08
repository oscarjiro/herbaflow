import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./handlers";

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

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
