import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@/lib/theme";
import { Stage7View, buildS7CsvRows, S7_CSV_HEADER } from "./Stage7View";
import { uniprotGeneUrl } from "../../lib/externalUrls";
import type { AnalysisRead } from "../../api/types.gen";
import * as sdk from "../../api/sdk.gen";

// ---------------------------------------------------------------------------
// Mock HubBarChart (uses Plotly/lazy) to avoid dynamic-import failures in jsdom.
// ---------------------------------------------------------------------------

vi.mock("@/components/charts/HubBarChart", () => ({
  HubBarChart: () => <div data-testid="hub-bar-chart" />,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeComputedResult() {
  return {
    state: "computed",
    hubs: [
      {
        rank: 1,
        target_id: "t0",
        gene_symbol: "TNF",
        degree: 0.41,
        betweenness: 0.33,
        closeness: 0.58,
        eigenvector: 0.29,
        mcc: 7,
        source_url: "https://www.uniprot.org/uniprotkb/P01375/entry",
      },
    ],
    ranking_metric: "mcc",
    node_count: 1,
    top_n: 20,
    count: 1,
    flags: [],
  };
}

const HUB_PARAM_VALUES = {
  top_n: 20,
};

function makeData(result: object): AnalysisRead {
  return {
    analysis_id: "11111111-1111-1111-1111-111111111111",
    status: "stage_7_awaiting_approval",
    current_stage: 7,
    parameters: { hub_genes: HUB_PARAM_VALUES },
    stage_results: {
      "7": result,
    },
    stage_state: {},
    plants: [],
    diseases: [],
    compounds: [],
  } as unknown as AnalysisRead;
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ThemeProvider>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </ThemeProvider>,
  );
}

async function openHubPanel() {
  await userEvent.click(screen.getByRole("button", { name: /hub-ranking parameters/i }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Stage7View", () => {
  it("renders the hub table with the gene and MCC", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByText("TNF")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("renders the cleaned small-network notice", () => {
    wrap(
      <Stage7View
        data={makeData({
          ...makeComputedResult(),
          flags: ["network_too_small"],
        })}
      />,
    );
    expect(
      screen.getByText(
        "The network is small or sparse. Centrality ranking is unreliable on trivial topology.",
      ),
    ).toBeInTheDocument();
  });

  it("renders summary cards for node count and hub count", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByLabelText(/1 nodes/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/1 hubs/i)).toBeInTheDocument();
  });

  it("renders the CSV download control", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    const link = screen.getByRole("link", { name: /download csv/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("download", "hubs.csv");
  });

  it("renders the hub_genes param panel with a Redo button", async () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    await openHubPanel();
    expect(screen.getByLabelText("Top N")).toBeInTheDocument();
    expect(screen.queryByLabelText("use_hub_bottleneck")).toBeNull();
    expect(screen.queryByLabelText("composite_weight")).toBeNull();
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument();
  });

  it("renders all four individual centrality columns", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByText("Degree")).toBeInTheDocument();
    expect(screen.getByText("Betweenness")).toBeInTheDocument();
    expect(screen.getByText("Closeness")).toBeInTheDocument();
    expect(screen.getByText("Eigenvector")).toBeInTheDocument();
  });

  it("passes every hub row to DataTable so the shared pager owns pagination", () => {
    const hubs = Array.from({ length: 12 }, (_, i) => ({
      rank: i + 1,
      target_id: `t${i}`,
      gene_symbol: `GENE${i}`,
      degree: 0.4,
      betweenness: 0.3,
      closeness: 0.5,
      eigenvector: 0.2,
      mcc: 12 - i,
      source_url: null,
    }));

    wrap(
      <Stage7View
        data={makeData({
          ...makeComputedResult(),
          hubs,
          node_count: hubs.length,
          count: hubs.length,
        })}
      />,
    );

    expect(screen.getByText("Showing 1–10 of 12")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Previous" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("rounds centralities to 4 sig figs and shows MCC as integer", () => {
    const result = {
      state: "computed",
      hubs: [
        {
          rank: 1,
          target_id: "t1",
          gene_symbol: "PPARG",
          degree: 0.123456789,
          betweenness: 0.5,
          closeness: 0.5,
          eigenvector: 0.5,
          mcc: 12,
          source_url: null,
        },
      ],
      ranking_metric: "mcc",
      node_count: 5,
      top_n: 10,
      count: 1,
      flags: [],
    };
    wrap(<Stage7View data={makeData(result)} />);
    expect(screen.getByText("0.1235")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("shows the hub gene chart frame when complete with hubs", () => {
    const completeData: AnalysisRead = {
      ...makeData(makeComputedResult()),
      status: "complete",
    } as unknown as AnalysisRead;
    wrap(<Stage7View data={completeData} />);
    // ChartFrame renders the title and a Download PNG button.
    expect(screen.getByText("Hub genes by centrality")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
    // The old server-rendered image must be gone.
    expect(screen.queryByRole("img", { name: /hub/i })).toBeNull();
  });

  it("shows the hub gene chart frame once the step has hubs, even before the run completes", () => {
    // The computed result has hubs on an awaiting-approval (not yet complete) run.
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    expect(screen.getByText("Hub genes by centrality")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
  });

  it("does not show the hub gene chart frame when there are no hubs", () => {
    wrap(
      <Stage7View
        data={makeData({
          ...makeComputedResult(),
          hubs: [],
          count: 0,
        })}
      />,
    );
    expect(screen.queryByText("Hub genes by centrality")).toBeNull();
    expect(screen.queryByRole("button", { name: /download png/i })).toBeNull();
  });

  it("links the gene symbol cell to UniProt via uniprotGeneUrl", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    // The gene-symbol cell is an anchor; its href must match uniprotGeneUrl for "TNF".
    const link = screen.getByRole("link", { name: "TNF" });
    expect(link).toHaveAttribute("href", uniprotGeneUrl("TNF"));
  });

  it("renders MCC and centrality values as numerics (not empty)", () => {
    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    // MCC = 7 (integer, unformatted)
    expect(screen.getByText("7")).toBeInTheDocument();
    // degree = 0.41 → formatSig → "0.41"
    expect(screen.getByText("0.41")).toBeInTheDocument();
    // betweenness = 0.33 → "0.33"
    expect(screen.getByText("0.33")).toBeInTheDocument();
    // closeness = 0.58 → "0.58"
    expect(screen.getByText("0.58")).toBeInTheDocument();
    // eigenvector = 0.29 → "0.29"
    expect(screen.getByText("0.29")).toBeInTheDocument();
  });
});

describe("Stage7View — CSV export", () => {
  it("CSV rows contain gene symbol and numerics but no UniProt link href", () => {
    const hubs = makeComputedResult().hubs;
    const rows = buildS7CsvRows(hubs);
    expect(rows).toHaveLength(1);
    const [rank, gene, mcc, degree, betweenness, closeness, eigenvector, source_url] = rows[0] as [
      number,
      string,
      number,
      number,
      number,
      number,
      number,
      string | null,
    ];
    expect(rank).toBe(1);
    expect(gene).toBe("TNF");
    expect(mcc).toBe(7);
    expect(degree).toBe(0.41);
    expect(betweenness).toBe(0.33);
    expect(closeness).toBe(0.58);
    expect(eigenvector).toBe(0.29);
    // source_url is the persisted URL field — present in CSV; no UniProt gene-search link injected.
    expect(source_url).toBe("https://www.uniprot.org/uniprotkb/P01375/entry");
    // The row has exactly 8 columns — no extra link column added.
    expect(rows[0]).toHaveLength(8);
    // No cell contains the uniprotGeneUrl pattern for a gene symbol.
    const rowStr = JSON.stringify(rows[0]);
    expect(rowStr).not.toContain("uniprotkb?query=gene:");
  });

  it("S7_CSV_HEADER does not contain a link column", () => {
    // Header must be exactly the persisted fields — gene_symbol only, no link.
    expect(S7_CSV_HEADER).toBe(
      "rank,gene_symbol,mcc,degree,betweenness,closeness,eigenvector,source_url",
    );
    expect(S7_CSV_HEADER).not.toContain("link");
    expect(S7_CSV_HEADER).not.toContain("url_link");
  });
});

describe("Stage7View — double-submit guards", () => {
  afterEach(() => vi.restoreAllMocks());

  it("disables the Redo button inside the param panel while the redo mutation is in-flight", async () => {
    vi.spyOn(sdk, "advanceAnalysis").mockResolvedValue({ data: {} } as never);
    // Never resolves so the redo mutation stays pending.
    vi.spyOn(sdk, "resetFrom").mockReturnValue(new Promise(() => {}));

    wrap(<Stage7View data={makeData(makeComputedResult())} />);
    await openHubPanel();

    // Change the top_n param so Redo becomes armed.
    const input = screen.getByLabelText("Top N");
    await userEvent.clear(input);
    await userEvent.type(input, "5");

    const redoBtn = screen.getByRole("button", { name: /redo/i });
    expect(redoBtn).not.toBeDisabled();

    await userEvent.click(redoBtn);
    expect(redoBtn).toBeDisabled();
  });
});
