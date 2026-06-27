import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { server } from "../../../tests/handlers";
import { setActiveRunId, getActiveRunId } from "@/lib/activeRun";
import { ExitRunDialog } from "./ExitRunDialog";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}
afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("ExitRunDialog", () => {
  it("deletes the run, clears storage, and calls onExited", async () => {
    server.use(
      http.delete(
        "http://localhost:8000/analyses/run-1",
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    setActiveRunId("run-1");
    const onExited = vi.fn();
    wrap(<ExitRunDialog analysisId="run-1" onExited={onExited} />);
    fireEvent.click(screen.getByRole("button", { name: /exit analysis/i }));
    fireEvent.click(await screen.findByRole("button", { name: /delete and exit/i }));
    await waitFor(() => expect(onExited).toHaveBeenCalledTimes(1));
    expect(getActiveRunId()).toBeNull();
  });

  it("renders the delete button as a red glass danger button (not a solid destructive fill)", async () => {
    setActiveRunId("run-1");
    wrap(<ExitRunDialog analysisId="run-1" onExited={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /exit analysis/i }));
    const del = await screen.findByRole("button", { name: /delete and exit/i });
    // Glass layered recipe with the danger tint hook — not the old solid fill.
    expect(del.className).toMatch(/hf-glass/);
    expect(del.className).toMatch(/hf-btn--danger/);
    expect(del.className).not.toMatch(/bg-destructive/);
    // Destructive color semantics kept: the label still reads red.
    const label = del.querySelector(".hf-glass__content");
    expect(label).not.toBeNull();
    expect(label!.className).toMatch(/text-hf-danger/);
  });

  it("keeps the run when delete fails", async () => {
    server.use(
      http.delete("http://localhost:8000/analyses/run-1", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    setActiveRunId("run-1");
    const onExited = vi.fn();
    wrap(<ExitRunDialog analysisId="run-1" onExited={onExited} />);
    fireEvent.click(screen.getByRole("button", { name: /exit analysis/i }));
    fireEvent.click(await screen.findByRole("button", { name: /delete and exit/i }));
    await waitFor(() => expect(getActiveRunId()).toBe("run-1"));
    expect(onExited).not.toHaveBeenCalled();
  });
});
