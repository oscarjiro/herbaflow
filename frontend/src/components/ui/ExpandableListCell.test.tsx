import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExpandableListCell } from "./ExpandableListCell";

const ITEMS_5 = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"];
const ITEMS_3 = ["Alpha", "Beta", "Gamma"];
const ITEMS_1 = ["Alpha"];

describe("ExpandableListCell — collapse / expand", () => {
  it("shows only collapsedCount chips + a '+N more' toggle when items exceed the limit", () => {
    render(<ExpandableListCell items={ITEMS_5} collapsedCount={3} />);

    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
    // Hidden in collapsed state
    expect(screen.queryByText("Delta")).not.toBeInTheDocument();
    expect(screen.queryByText("Epsilon")).not.toBeInTheDocument();

    const toggle = screen.getByRole("button", { name: /\+2 more/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("reveals all chips after clicking the '+N more' toggle", () => {
    render(<ExpandableListCell items={ITEMS_5} collapsedCount={3} />);

    fireEvent.click(screen.getByRole("button", { name: /\+2 more/i }));

    expect(screen.getByText("Delta")).toBeInTheDocument();
    expect(screen.getByText("Epsilon")).toBeInTheDocument();

    const showLess = screen.getByRole("button", { name: /show less/i });
    expect(showLess).toBeInTheDocument();
    expect(showLess).toHaveAttribute("aria-expanded", "true");
  });

  it("collapses back to collapsedCount chips after clicking 'Show less'", () => {
    render(<ExpandableListCell items={ITEMS_5} collapsedCount={3} />);

    fireEvent.click(screen.getByRole("button", { name: /\+2 more/i }));
    fireEvent.click(screen.getByRole("button", { name: /show less/i }));

    expect(screen.queryByText("Delta")).not.toBeInTheDocument();
    expect(screen.queryByText("Epsilon")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+2 more/i })).toBeInTheDocument();
  });
});

describe("ExpandableListCell — no toggle when within limit", () => {
  it("renders all items and no toggle when items.length equals collapsedCount", () => {
    render(<ExpandableListCell items={ITEMS_3} collapsedCount={3} />);

    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders all items and no toggle when items.length is less than collapsedCount", () => {
    render(<ExpandableListCell items={ITEMS_1} collapsedCount={3} />);

    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("ExpandableListCell — empty list", () => {
  it("renders a muted placeholder for an empty items array", () => {
    render(<ExpandableListCell items={[]} />);

    // The "–" placeholder should be present
    expect(screen.getByText("–")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("ExpandableListCell — renderItem", () => {
  it("uses renderItem to wrap each chip's content when provided", () => {
    render(
      <ExpandableListCell
        items={["CID:001", "CID:002", "CID:003"]}
        collapsedCount={3}
        renderItem={(v) => <strong data-testid="wrapped">{v}</strong>}
      />,
    );

    const wrapped = screen.getAllByTestId("wrapped");
    expect(wrapped).toHaveLength(3);
    expect(wrapped[0]).toHaveTextContent("CID:001");
  });

  it("uses renderItem only for visible items in collapsed state", () => {
    render(
      <ExpandableListCell
        items={["A", "B", "C", "D", "E"]}
        collapsedCount={2}
        renderItem={(v) => <em data-testid="em">{v}</em>}
      />,
    );

    // Only 2 visible chips in collapsed state
    expect(screen.getAllByTestId("em")).toHaveLength(2);
  });
});
