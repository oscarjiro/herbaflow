import { humanizeProblem, isServiceOutage } from "./problem";

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

test("isServiceOutage flags a backend-up-but-store-unreachable outage (402, 503)", () => {
  expect(isServiceOutage({ status: 402 })).toBe(true); // hosted DB over its usage limit
  expect(isServiceOutage({ status: 503 })).toBe(true); // DB unreachable (mapped OSError)
});

test("isServiceOutage is false for ordinary errors and nullish input", () => {
  expect(isServiceOutage({ status: 404 })).toBe(false);
  expect(isServiceOutage({ status: 422 })).toBe(false);
  expect(isServiceOutage({ status: 500 })).toBe(false);
  expect(isServiceOutage(undefined)).toBe(false);
  expect(isServiceOutage(null)).toBe(false);
});
