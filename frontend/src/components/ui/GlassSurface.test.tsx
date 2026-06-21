import { render } from "@testing-library/react";
import { GlassSurface } from "./GlassSurface";

// jsdom cannot evaluate @supports or @media, so we test the structural contract:
// the 4 layers render with the right classes, the tier modifier is applied,
// and className/children pass through.

describe("GlassSurface — layer structure", () => {
  it("renders the 4 glass layers by default (overlay tier)", () => {
    const { container } = render(<GlassSurface>content</GlassSurface>);
    const root = container.firstElementChild!;
    expect(root.querySelector(".hf-glass__refract")).toBeTruthy();
    expect(root.querySelector(".hf-glass__tint")).toBeTruthy();
    expect(root.querySelector(".hf-glass__shine")).toBeTruthy();
    expect(root.querySelector(".hf-glass__content")).toBeTruthy();
  });

  it("root element has .hf-glass base class", () => {
    const { container } = render(<GlassSurface>hi</GlassSurface>);
    expect(container.firstElementChild).toHaveClass("hf-glass");
  });

  it("default tier is overlay → .hf-glass--overlay on root", () => {
    const { container } = render(<GlassSurface>hi</GlassSurface>);
    expect(container.firstElementChild).toHaveClass("hf-glass--overlay");
  });
});

describe("GlassSurface — tier prop", () => {
  it("tier=chrome adds .hf-glass--chrome", () => {
    const { container } = render(<GlassSurface tier="chrome">x</GlassSurface>);
    expect(container.firstElementChild).toHaveClass("hf-glass--chrome");
    expect(container.firstElementChild).not.toHaveClass("hf-glass--overlay");
    expect(container.firstElementChild).not.toHaveClass("hf-glass--raised");
  });

  it("tier=overlay adds .hf-glass--overlay", () => {
    const { container } = render(<GlassSurface tier="overlay">x</GlassSurface>);
    expect(container.firstElementChild).toHaveClass("hf-glass--overlay");
  });

  it("tier=raised adds .hf-glass--raised", () => {
    const { container } = render(<GlassSurface tier="raised">x</GlassSurface>);
    expect(container.firstElementChild).toHaveClass("hf-glass--raised");
    expect(container.firstElementChild).not.toHaveClass("hf-glass--overlay");
  });
});

describe("GlassSurface — passthrough", () => {
  it("children render inside .hf-glass__content", () => {
    const { container } = render(
      <GlassSurface>
        <span data-testid="child">hello</span>
      </GlassSurface>,
    );
    const content = container.querySelector(".hf-glass__content");
    expect(content?.querySelector("[data-testid='child']")).toBeTruthy();
  });

  it("className is merged onto the root element", () => {
    const { container } = render(<GlassSurface className="my-custom-class">x</GlassSurface>);
    expect(container.firstElementChild).toHaveClass("my-custom-class");
    expect(container.firstElementChild).toHaveClass("hf-glass");
  });

  it("extra HTML props spread onto the root element", () => {
    const { container } = render(<GlassSurface data-testid="gs-root">x</GlassSurface>);
    expect(container.querySelector("[data-testid='gs-root']")).toBeTruthy();
  });
});
