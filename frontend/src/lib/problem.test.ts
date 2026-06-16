import { humanizeProblem } from "./problem";

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
