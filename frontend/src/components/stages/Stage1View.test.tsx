import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { Stage1View } from "./Stage1View";
import * as sdk from "../../api/sdk.gen";

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

/** Minimal stage1 data whose compound set already contains C1/Quercetin. */
function makeStage1(overrides?: Partial<Parameters<typeof Stage1View>[0]["stage1"]>) {
  return {
    count: 1,
    compounds: [{ compound_id: "C1", canonical_name: "Quercetin", tag: "computed" }],
    state: "computed",
    ...overrides,
  };
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Stage1View — already-in-run deduplication", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an already-in-run note and skips the duplicate in the edit call", async () => {
    // Mock editStage so the mutation doesn't actually fetch
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    // Mock validateCompounds to return C1 (already in run) + C2 (new)
    vi.spyOn(sdk, "validateCompounds").mockResolvedValue({
      data: {
        resolved: [
          { compound_id: "C1", canonical_name: "Quercetin", canonical_key: "quercetin" },
          { compound_id: "C2", canonical_name: "Kaempferol", canonical_key: "kaempferol" },
        ],
        failed: [],
      },
    } as never);

    wrap(<Stage1View analysisId="a1" stage1={makeStage1()} />);

    // Type something in the CompoundValidateBox textarea and click Validate
    const textarea = screen.getByRole("textbox", { name: /add compounds/i });
    await userEvent.type(textarea, "Quercetin\nKaempferol");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));

    // Wait for resolved list to appear, then click Add
    await waitFor(() => screen.getByRole("list", { name: /resolved compounds/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // The note should appear, naming Quercetin
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/already in run/i));
    expect(screen.getByRole("status")).toHaveTextContent("Quercetin");

    // editStage should have been called with only the new id (C2)
    expect(editSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        path: { analysis_id: "a1", stage: 1 },
        body: { add: ["C2"], remove: [] },
      }),
    );
    // editStage should NOT have been called with C1
    for (const call of editSpy.mock.calls) {
      expect((call[0] as { body: { add: string[] } }).body.add).not.toContain("C1");
    }
  });

  it("does not show the note when all resolved compounds are new", async () => {
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    vi.spyOn(sdk, "validateCompounds").mockResolvedValue({
      data: {
        resolved: [
          { compound_id: "C3", canonical_name: "Rutin", canonical_key: "rutin" },
        ],
        failed: [],
      },
    } as never);

    wrap(<Stage1View analysisId="a1" stage1={makeStage1()} />);

    const textarea = screen.getByRole("textbox", { name: /add compounds/i });
    await userEvent.type(textarea, "Rutin");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() => screen.getByRole("list", { name: /resolved compounds/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(editSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          body: { add: ["C3"], remove: [] },
        }),
      ),
    );

    // No "already in run" note
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("does not call editStage when all resolved compounds are duplicates", async () => {
    const editSpy = vi.spyOn(sdk, "editStage").mockResolvedValue({ data: {} } as never);

    vi.spyOn(sdk, "validateCompounds").mockResolvedValue({
      data: {
        resolved: [
          { compound_id: "C1", canonical_name: "Quercetin", canonical_key: "quercetin" },
        ],
        failed: [],
      },
    } as never);

    wrap(<Stage1View analysisId="a1" stage1={makeStage1()} />);

    const textarea = screen.getByRole("textbox", { name: /add compounds/i });
    await userEvent.type(textarea, "Quercetin");
    await userEvent.click(screen.getByRole("button", { name: /^validate$/i }));
    await waitFor(() => screen.getByRole("list", { name: /resolved compounds/i }));
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));

    // Note appears
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/already in run/i));
    // editStage should NOT have been called at all
    expect(editSpy).not.toHaveBeenCalled();
  });
});
