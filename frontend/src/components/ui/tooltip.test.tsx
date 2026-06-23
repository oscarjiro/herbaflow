import { render } from "@testing-library/react";
import { TooltipContent, TooltipProvider, Tooltip, TooltipTrigger } from "./tooltip";

// Radix renders TooltipContent into a Portal; by default in jsdom that means
// document.body. We open the tooltip by rendering it with defaultOpen so the
// content is always in the DOM without needing pointer events.

function renderTooltip() {
  return render(
    <TooltipProvider>
      <Tooltip defaultOpen>
        <TooltipTrigger>trigger</TooltipTrigger>
        <TooltipContent>tip text</TooltipContent>
      </Tooltip>
    </TooltipProvider>,
  );
}

describe("TooltipContent — explicit inverted surface tokens", () => {
  it("uses explicit bg-hf-fg-1 (not aliased bg-foreground)", () => {
    renderTooltip();
    const content = document.querySelector("[data-slot='tooltip-content']");
    expect(content).toBeTruthy();
    expect(content!.className).toContain("bg-hf-fg-1");
    expect(content!.className).not.toContain("bg-foreground");
  });

  it("uses explicit text-hf-bg (not aliased text-background)", () => {
    renderTooltip();
    const content = document.querySelector("[data-slot='tooltip-content']");
    expect(content!.className).toContain("text-hf-bg");
    expect(content!.className).not.toContain("text-background");
  });

  it("has mockup-faithful padding px-3 py-1.5", () => {
    renderTooltip();
    const content = document.querySelector("[data-slot='tooltip-content']");
    expect(content!.className).toContain("px-3");
    expect(content!.className).toContain("py-1.5");
  });

  it("has small text-xs size", () => {
    renderTooltip();
    const content = document.querySelector("[data-slot='tooltip-content']");
    expect(content!.className).toContain("text-xs");
  });

  it("has rounded-md radius", () => {
    renderTooltip();
    const content = document.querySelector("[data-slot='tooltip-content']");
    expect(content!.className).toContain("rounded-md");
  });

  it("arrow uses fill-hf-fg-1 (not fill-foreground)", () => {
    renderTooltip();
    // The Radix Arrow is rendered as an SVG inside the tooltip content wrapper.
    // Check the raw portal HTML for the fill class so we don't need to traverse
    // Radix internals.
    const portalHtml = document.body.innerHTML;
    expect(portalHtml).toContain("fill-hf-fg-1");
    expect(portalHtml).not.toContain("fill-foreground");
  });
});
