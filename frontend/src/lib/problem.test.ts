import { humanizeProblem, isHardDown } from "./problem";

test("maps a problem+json body to a plain declarative string", () => {
  const msg = humanizeProblem({
    type: "about:blank",
    title: "Service Unavailable",
    status: 503,
    detail: "Upstream provider is temporarily unavailable.",
  });
  expect(msg).toBe("Upstream provider is temporarily unavailable.");
});

test("falls back to title, then a generic line", () => {
  expect(humanizeProblem({ status: 500, title: "Internal Server Error" } as never)).toBe(
    "Internal Server Error",
  );
  expect(humanizeProblem(undefined)).toBe("Something went wrong. Please try again.");
});

test("isHardDown flags a store-down status (402, 503)", () => {
  expect(isHardDown({ status: 402 })).toBe(true); // hosted DB over its usage limit
  expect(isHardDown({ status: 503 })).toBe(true); // DB unreachable (mapped OSError)
});

test("isHardDown flags a transport failure (error with no HTTP status)", () => {
  // A fetch that never reaches the backend throws with no `.status` — the run page
  // must surface the service-unavailable screen rather than poll forever.
  expect(isHardDown({} as never)).toBe(true);
  expect(isHardDown(new TypeError("Failed to fetch") as never)).toBe(true);
});

test("isHardDown is false for self-healable statuses and nullish input", () => {
  expect(isHardDown({ status: 404 })).toBe(false); // gone → cleared back to setup
  expect(isHardDown({ status: 422 })).toBe(false); // malformed id → cleared back to setup
  expect(isHardDown({ status: 500 })).toBe(false); // transient server error → inline retry
  expect(isHardDown(undefined)).toBe(false);
  expect(isHardDown(null)).toBe(false);
});
