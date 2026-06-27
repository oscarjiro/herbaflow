import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

// PageTransition reads the current pathname via TanStack Router's useRouterState.
// We stub that boundary so the component can render without a full RouterProvider.
const pathnameRef = { current: "/" };
vi.mock("@tanstack/react-router", () => ({
  useRouterState: (opts: { select: (s: unknown) => unknown }) =>
    opts.select({ location: { pathname: pathnameRef.current } }),
}));

import { PageTransition, sectionKey } from "./PageTransition";

describe("sectionKey", () => {
  test("Landing is its own section", () => {
    expect(sectionKey("/")).toBe("/");
  });

  test("About is its own section", () => {
    expect(sectionKey("/about")).toBe("/about");
    expect(sectionKey("/about/")).toBe("/about");
  });

  test("the analysis entry route is the analysis section", () => {
    expect(sectionKey("/analysis")).toBe("/analysis");
  });

  test("a run route stays in the analysis section", () => {
    expect(sectionKey("/analysis/abc123")).toBe("/analysis");
  });

  test("stage routes stay in the analysis section (no remount between stages)", () => {
    expect(sectionKey("/analysis/abc123/3")).toBe("/analysis");
    expect(sectionKey("/analysis/abc123/7")).toBe("/analysis");
  });
});

describe("PageTransition", () => {
  test("renders its children", () => {
    pathnameRef.current = "/about";
    render(
      <PageTransition>
        <p>page body</p>
      </PageTransition>,
    );
    expect(screen.getByText("page body")).toBeInTheDocument();
  });
});
