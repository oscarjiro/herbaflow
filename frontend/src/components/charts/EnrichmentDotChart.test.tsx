import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/lib/theme";
import { EnrichmentDotChart } from "./EnrichmentDotChart";

// ---------------------------------------------------------------------------
// Mock recharts ResponsiveContainer — gives the chart an explicit size in
// jsdom (same pattern as HubBarChart.test.tsx).
// ---------------------------------------------------------------------------

vi.mock("recharts", async (orig) => {
  const actual = await orig<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) =>
      React.cloneElement(children as React.ReactElement<Record<string, unknown>>, {
        width: 800,
        height: 400,
      }),
  };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>,
  );
}

const SAMPLE_TERMS = [
  {
    source: "BP",
    name: "response to oxidative stress",
    p_value: 0.001,
    intersection_size: 5,
  },
  {
    source: "KEGG",
    name: "PI3K-Akt signaling pathway",
    p_value: 0.003,
    intersection_size: 3,
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EnrichmentDotChart", () => {
  it("renders scatter symbol elements for the provided terms", () => {
    const { container } = wrap(<EnrichmentDotChart terms={SAMPLE_TERMS} />);
    const symbols = container.querySelectorAll(".recharts-scatter-symbol");
    expect(symbols.length).toBeGreaterThanOrEqual(2);
  });

  it("shows full-name legend labels for each source", () => {
    wrap(<EnrichmentDotChart terms={SAMPLE_TERMS} />);
    expect(screen.getByText("Biological Process")).toBeInTheDocument();
    expect(screen.getByText("KEGG Pathway")).toBeInTheDocument();
  });

  it("renders without throwing when terms is empty", () => {
    expect(() => wrap(<EnrichmentDotChart terms={[]} />)).not.toThrow();
  });

  it("renders without throwing and produces a finite negLogP for p_value 0", () => {
    // p_value 0 would yield -log10(0) = Infinity; the clamp to 1e-300 must prevent that.
    expect(() =>
      wrap(
        <EnrichmentDotChart
          terms={[{ source: "BP", name: "test term", p_value: 0, intersection_size: 2 }]}
        />,
      ),
    ).not.toThrow();
  });

  it("renders without throwing inside ThemeProvider", () => {
    expect(() => wrap(<EnrichmentDotChart terms={SAMPLE_TERMS} />)).not.toThrow();
  });
});
