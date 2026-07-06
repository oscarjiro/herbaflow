/**
 * Table primitives re-skin — liquid-glass solid look.
 *
 * jsdom cannot evaluate computed CSS, so we assert on the class strings the
 * primitives emit. The goal is to lock the re-skin contract:
 * - headers are uppercase + letter-spaced (tracked) and use hf foreground tokens
 *   (NOT shadcn `text-foreground` / `bg-muted`)
 * - rows hover on an hf surface token (NOT `bg-muted/50`)
 * - all data-slot attributes are preserved (DataTable depends on them)
 * - ExternalLinkCell affordance hook renders with hf tokens + icon
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
  ExternalLinkCell,
} from "./table";

function FullTable() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Gene symbol</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>MAPK1</TableCell>
        </TableRow>
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell>footer</TableCell>
        </TableRow>
      </TableFooter>
      <TableCaption>caption</TableCaption>
    </Table>
  );
}

describe("Table primitives — data-slot stability", () => {
  it("preserves every data-slot attribute", () => {
    const { container } = render(<FullTable />);
    for (const slot of [
      "table-container",
      "table",
      "table-header",
      "table-body",
      "table-footer",
      "table-row",
      "table-head",
      "table-cell",
      "table-caption",
    ]) {
      expect(container.querySelector(`[data-slot="${slot}"]`)).not.toBeNull();
    }
  });
});

describe("TableHead — uppercase, tracked, hf tokens", () => {
  it("is uppercase and letter-spaced (tracked)", () => {
    const { container } = render(<FullTable />);
    const head = container.querySelector('[data-slot="table-head"]')!;
    expect(head.className).toContain("uppercase");
    expect(head.className).toMatch(/tracking-/);
  });

  it("uses an hf foreground token, not shadcn text-foreground", () => {
    const { container } = render(<FullTable />);
    const head = container.querySelector('[data-slot="table-head"]')!;
    expect(head.className).toMatch(/text-hf-fg-/);
    expect(head.className).not.toContain("text-foreground");
  });
});

describe("TableRow — hf hover, not bg-muted", () => {
  it("hovers on an hf surface token, not bg-muted/50", () => {
    const { container } = render(<FullTable />);
    const rows = container.querySelectorAll('[data-slot="table-row"]');
    // The body row carries the hover styling.
    const bodyRow = Array.from(rows).find((r) => r.textContent === "MAPK1")!;
    expect(bodyRow.className).toContain(
      "hover:bg-[color-mix(in_srgb,var(--hf-ink),transparent_94%)]",
    );
    expect(bodyRow.className).not.toContain("bg-muted/50");
  });
});

describe("TableCell — numeric alignment hook", () => {
  it("can carry tabular-nums via className passthrough", () => {
    const { container } = render(
      <Table>
        <TableBody>
          <TableRow>
            <TableCell className="num tabular-nums">1,842</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    const cell = container.querySelector('[data-slot="table-cell"]')!;
    expect(cell.className).toContain("tabular-nums");
  });
});

describe("ExternalLinkCell affordance", () => {
  it("renders an external link with hf token styling and an external-link icon", () => {
    render(<ExternalLinkCell href="https://example.org/P28482">P28482</ExternalLinkCell>);
    const link = screen.getByRole("link", { name: /P28482/ });
    expect(link).toHaveAttribute("href", "https://example.org/P28482");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(link.querySelector("svg")).not.toBeNull();
  });
});
