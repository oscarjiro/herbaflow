import { cleanup, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { server } from "../../tests/handlers";
import { renderWithRouter } from "../../tests/renderWithRouter";
import { setActiveRunId } from "@/lib/activeRun";
import { AnalysisGate } from "./AnalysisGate";

const HEALTH = "http://localhost:8000/health";
afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("AnalysisGate", () => {
  it("shows ServiceUnavailable when health fails", async () => {
    server.use(http.get(HEALTH, () => HttpResponse.json({ detail: "db down" }, { status: 503 })));
    renderWithRouter(<AnalysisGate />, { initialEntries: ["/analysis"] });
    await screen.findByRole("alert");
    expect(screen.getByText(/service unavailable/i)).toBeInTheDocument();
  });

  it("renders Setup when healthy and no active run", async () => {
    server.use(http.get(HEALTH, () => HttpResponse.json({ status: "ok" })));
    renderWithRouter(<AnalysisGate />, { initialEntries: ["/analysis"] });
    // SetupView renders "Plant input" as its first card title (unique, exact).
    await screen.findByText("Plant input");
  });

  it("redirects to the active run when one is cached", async () => {
    server.use(http.get(HEALTH, () => HttpResponse.json({ status: "ok" })));
    setActiveRunId("run-xyz");
    const { router } = renderWithRouter(<AnalysisGate />, { initialEntries: ["/analysis"] });
    await waitFor(() => expect(router.state.location.pathname).toBe("/analysis/run-xyz"));
  });
});
