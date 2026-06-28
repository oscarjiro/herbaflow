import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardContent, CardTitle } from "./card";

describe("Card — solid (opt-in variant)", () => {
  it("renders data-slot=card", () => {
    render(<Card variant="solid">content</Card>);
    const card = document.querySelector("[data-slot='card']");
    expect(card).not.toBeNull();
  });

  it("does not render hf-glass class when variant=solid", () => {
    render(<Card variant="solid">solid</Card>);
    const card = document.querySelector("[data-slot='card']");
    expect(card?.className).not.toContain("hf-glass");
  });

  it("renders children in solid mode", () => {
    render(
      <Card variant="solid">
        <CardTitle>My card</CardTitle>
      </Card>,
    );
    expect(screen.getByText("My card")).toBeInTheDocument();
  });
});

describe("Card — glass raised (default)", () => {
  it("renders glass by default (no variant prop)", () => {
    render(<Card>glass by default</Card>);
    const glassEl = document.querySelector(".hf-glass");
    expect(glassEl).not.toBeNull();
    expect(glassEl?.className).toContain("hf-glass--raised");
  });

  it("renders hf-glass and hf-glass--raised classes when variant=glass-raised", () => {
    render(<Card variant="glass-raised">glass content</Card>);
    const glassEl = document.querySelector(".hf-glass");
    expect(glassEl).not.toBeNull();
    expect(glassEl?.className).toContain("hf-glass--raised");
  });

  it("renders the four GlassSurface layers (refract, tint, shine, content)", () => {
    render(<Card variant="glass-raised">inside</Card>);
    expect(document.querySelector(".hf-glass__refract")).not.toBeNull();
    expect(document.querySelector(".hf-glass__tint")).not.toBeNull();
    expect(document.querySelector(".hf-glass__shine")).not.toBeNull();
    expect(document.querySelector(".hf-glass__content")).not.toBeNull();
  });

  it("renders children inside glass content layer", () => {
    render(
      <Card variant="glass-raised">
        <CardContent>stat</CardContent>
      </Card>,
    );
    expect(screen.getByText("stat")).toBeInTheDocument();
  });

  it("passes additional className to the outer element", () => {
    render(
      <Card variant="glass-raised" className="extra-class">
        x
      </Card>,
    );
    const el = document.querySelector(".hf-glass");
    expect(el?.className).toContain("extra-class");
  });
});
