import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/lib/theme";
import { HubBarChart } from "./HubBarChart";

// ---------------------------------------------------------------------------
// Mock recharts ResponsiveContainer — it renders 0-size in jsdom which
// prevents child charts from mounting at all.
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

const SAMPLE_HUBS = [
  { gene_symbol: "TNF", mcc: 42 },
  { gene_symbol: "TP53", mcc: 37 },
  { gene_symbol: "PPARG", mcc: 15 },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HubBarChart", () => {
  it("renders one bar rectangle per hub", () => {
    const { container } = wrap(<HubBarChart hubs={SAMPLE_HUBS} />);
    // recharts renders each bar as a <path> or <rect> inside .recharts-bar-rectangle
    const bars = container.querySelectorAll(".recharts-bar-rectangle");
    expect(bars.length).toBe(3);
  });

  it("renders each gene symbol as a Y-axis label", () => {
    wrap(<HubBarChart hubs={SAMPLE_HUBS} />);
    expect(screen.getByText("TNF")).toBeInTheDocument();
    expect(screen.getByText("TP53")).toBeInTheDocument();
    expect(screen.getByText("PPARG")).toBeInTheDocument();
  });

  it("renders inside a ThemeProvider without throwing", () => {
    expect(() => wrap(<HubBarChart hubs={SAMPLE_HUBS} />)).not.toThrow();
  });

  it("renders without throwing when hubs is empty", () => {
    expect(() => wrap(<HubBarChart hubs={[]} />)).not.toThrow();
  });

  it("renders zero bars for empty data", () => {
    const { container } = wrap(<HubBarChart hubs={[]} />);
    const bars = container.querySelectorAll(".recharts-bar-rectangle");
    expect(bars.length).toBe(0);
  });
});
