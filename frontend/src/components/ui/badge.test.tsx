import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./badge";

const statusVariants = ["success", "warning", "danger", "info", "neutral"] as const;

describe("Badge — status variants", () => {
  it.each(statusVariants)("variant=%s renders data-variant attribute", (variant) => {
    render(<Badge variant={variant}>label</Badge>);
    const badge = screen.getByText("label");
    expect(badge.getAttribute("data-variant")).toBe(variant);
  });

  it("success variant has success-soft background token class", () => {
    render(<Badge variant="success">OK</Badge>);
    const badge = screen.getByText("OK");
    expect(badge.className).toContain("bg-hf-success-soft/70");
    expect(badge.className).toContain("text-hf-success");
  });

  it("warning variant has warning-soft background token class", () => {
    render(<Badge variant="warning">Warn</Badge>);
    const badge = screen.getByText("Warn");
    expect(badge.className).toContain("bg-hf-warning-soft/70");
    expect(badge.className).toContain("text-hf-warning");
  });

  it("danger variant has danger-soft background token class", () => {
    render(<Badge variant="danger">Err</Badge>);
    const badge = screen.getByText("Err");
    expect(badge.className).toContain("bg-hf-danger-soft/70");
    expect(badge.className).toContain("text-hf-danger");
  });

  it("info variant has info-soft background token class", () => {
    render(<Badge variant="info">Info</Badge>);
    const badge = screen.getByText("Info");
    expect(badge.className).toContain("bg-hf-info-soft/70");
    expect(badge.className).toContain("text-hf-info");
  });

  it("neutral variant has surface-2 background and border", () => {
    render(<Badge variant="neutral">Source</Badge>);
    const badge = screen.getByText("Source");
    expect(badge.className).toContain("bg-hf-surface-2/70");
    expect(badge.className).toContain("text-hf-fg-3");
    expect(badge.className).toContain("border-hf-border");
  });

  it("existing default variant still renders", () => {
    render(<Badge variant="default">Default</Badge>);
    const badge = screen.getByText("Default");
    expect(badge.getAttribute("data-variant")).toBe("default");
  });
});
