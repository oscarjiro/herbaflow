import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChartFrame } from "./ChartFrame";

// ---------------------------------------------------------------------------
// Module mocks (declared before any imports that trigger the modules)
// ---------------------------------------------------------------------------
vi.mock("@/lib/chartExport", () => ({
  exportSvgAsPng: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/toast", () => ({
  notifySuccess: vi.fn(),
  notifyError: vi.fn(),
  notifyInfo: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Import the mocked modules so we can assert on them
// ---------------------------------------------------------------------------
import * as chartExport from "@/lib/chartExport";
import * as toast from "@/lib/toast";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function renderFrame(props: Partial<React.ComponentProps<typeof ChartFrame>> = {}) {
  return render(
    <ChartFrame title="Hub genes by MCC" filename="hub_genes_mcc.png" {...props}>
      <svg data-testid="chart" viewBox="0 0 10 10" />
    </ChartFrame>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("ChartFrame — rendering", () => {
  it("renders the title", () => {
    renderFrame();
    expect(screen.getByText("Hub genes by MCC")).toBeInTheDocument();
  });

  it("renders a Download PNG button", () => {
    renderFrame();
    expect(screen.getByRole("button", { name: /download png/i })).toBeInTheDocument();
  });

  it("renders children", () => {
    renderFrame();
    expect(screen.getByTestId("chart")).toBeInTheDocument();
  });

  it("renders the description when provided", () => {
    renderFrame({ description: "Top 10 hub genes ranked by MCC score" });
    expect(screen.getByText("Top 10 hub genes ranked by MCC score")).toBeInTheDocument();
  });

  it("does not render a description element when omitted", () => {
    renderFrame();
    expect(screen.queryByText("Top 10 hub genes ranked by MCC score")).not.toBeInTheDocument();
  });
});

describe("ChartFrame — default export (calls exportSvgAsPng)", () => {
  beforeEach(() => {
    vi.mocked(chartExport.exportSvgAsPng).mockResolvedValue(undefined);
    vi.mocked(toast.notifySuccess).mockClear();
    vi.mocked(toast.notifyError).mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls exportSvgAsPng with the SVGElement and correct opts on button click", async () => {
    const user = userEvent.setup();
    renderFrame();
    await user.click(screen.getByRole("button", { name: /download png/i }));
    expect(chartExport.exportSvgAsPng).toHaveBeenCalledWith(expect.any(SVGElement), {
      title: "Hub genes by MCC",
      filename: "hub_genes_mcc.png",
    });
  });

  it("calls notifySuccess after a successful export", async () => {
    const user = userEvent.setup();
    renderFrame();
    await user.click(screen.getByRole("button", { name: /download png/i }));
    expect(toast.notifySuccess).toHaveBeenCalledWith(expect.stringContaining("Hub genes by MCC"));
  });

  it("calls notifyError when exportSvgAsPng rejects", async () => {
    const err = { status: 500, title: "Export failed" };
    vi.mocked(chartExport.exportSvgAsPng).mockRejectedValue(err);
    const user = userEvent.setup();
    renderFrame();
    await user.click(screen.getByRole("button", { name: /download png/i }));
    expect(toast.notifyError).toHaveBeenCalledWith(err);
  });
});

describe("ChartFrame — custom onExport prop", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls the onExport prop instead of exportSvgAsPng", async () => {
    const onExport = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderFrame({ onExport });
    await user.click(screen.getByRole("button", { name: /download png/i }));
    expect(onExport).toHaveBeenCalledTimes(1);
    expect(chartExport.exportSvgAsPng).not.toHaveBeenCalled();
  });

  it("calls notifySuccess when the custom onExport resolves", async () => {
    const onExport = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderFrame({ onExport });
    await user.click(screen.getByRole("button", { name: /download png/i }));
    expect(toast.notifySuccess).toHaveBeenCalled();
  });
});
