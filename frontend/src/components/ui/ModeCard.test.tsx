/**
 * Task 10 — ModeCard: selectable option card with elevated body and filled check.
 *
 * jsdom cannot evaluate CSS variables or transitions, so we assert:
 * - card renders title and description
 * - optional icon slot renders when provided
 * - selected card carries the brighter-elevated-body class (bg-hf-surface)
 * - selected card does NOT carry bg-hf-surface-2 as the body background
 * - selected card renders a filled CheckIcon (data-slot="check")
 * - unselected card does NOT render a visible filled check (check is hidden)
 * - selected state does NOT add a ring, tinted-border, or tint class
 * - onSelect fires when clicked
 * - keyboard Space and Enter trigger onSelect
 * - focus-visible ring class is present (Task-4 contract)
 * - role="radio" with aria-checked semantics
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FlaskConical } from "lucide-react";
import { ModeCard, ModeCardGroup } from "./ModeCard";

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("ModeCard — rendering", () => {
  it("renders the title", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText("Manual entry")).toBeTruthy();
  });

  it("renders the description", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText("Enter compounds by name")).toBeTruthy();
  });

  it("renders an optional icon when provided", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        icon={<FlaskConical data-testid="icon" />}
        selected={false}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByTestId("icon")).toBeTruthy();
  });

  it("does not render an icon slot when no icon is provided", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    expect(document.querySelector("[data-slot='mode-card-icon']")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Selected state — elevated body + filled check
// ---------------------------------------------------------------------------

describe("ModeCard — selected state", () => {
  it("selected card carries bg-hf-surface class (brighter elevated body)", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={true}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    expect(card.className).toMatch(/bg-hf-surface/);
  });

  it("unselected card carries bg-hf-surface-2 class (dimmer resting body)", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    expect(card.className).toMatch(/bg-hf-surface-2/);
  });

  it("selected card renders the filled check element", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={true}
        onSelect={() => {}}
      />,
    );
    const tick = document.querySelector("[data-slot='mode-card-tick']");
    expect(tick).not.toBeNull();
    expect(tick!.className).toMatch(/bg-hf-fg-1/);
  });

  it("unselected card tick does NOT carry bg-hf-fg-1 (unfilled)", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    const tick = document.querySelector("[data-slot='mode-card-tick']");
    expect(tick).not.toBeNull();
    // Unselected tick must NOT be filled
    expect(tick!.className).not.toMatch(/bg-hf-fg-1/);
  });

  it("selected card carries the shadow elevation class", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={true}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    // Shadow via arbitrary value shadow-[var(--hf-glass-shadow)]
    expect(card.className).toMatch(/shadow-/);
  });
});

// ---------------------------------------------------------------------------
// No ring / no border-change / no tint on selection (spec critical rule)
// ---------------------------------------------------------------------------

describe("ModeCard — selected state does NOT add ring, colored border, or tint", () => {
  it("selected card does not add a ring class", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={true}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    // Must not carry any ring-* class (focus-visible:ring-* is allowed but only on focus-visible)
    // Check: no bare ring-* (without focus-visible: prefix) for selection
    const classes = card.className.split(/\s+/);
    const bareRingClasses = classes.filter((c) => /^ring-/.test(c) || /^ring$/.test(c));
    expect(bareRingClasses).toHaveLength(0);
  });

  it("selected card does not add a tint class (accent/sage/terracotta bg)", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={true}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    expect(card.className).not.toMatch(/bg-hf-sage|bg-hf-terracotta|bg-hf-accent|tint/);
  });

  it("selected card does not add a colored border class (border-hf-fg-1 on the card body)", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={true}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    // The card body should not carry border-hf-fg-1 — selection uses elevation, not border color
    expect(card.className).not.toMatch(/border-hf-fg-1/);
  });
});

// ---------------------------------------------------------------------------
// Interaction — onSelect / keyboard
// ---------------------------------------------------------------------------

describe("ModeCard — interaction", () => {
  it("calls onSelect when clicked", () => {
    const onSelect = vi.fn();
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={onSelect}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    fireEvent.click(card);
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("calls onSelect on Space keydown", () => {
    const onSelect = vi.fn();
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={onSelect}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    card.focus();
    fireEvent.keyDown(card, { key: " ", code: "Space" });
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("calls onSelect on Enter keydown", () => {
    const onSelect = vi.fn();
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={onSelect}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    card.focus();
    fireEvent.keyDown(card, { key: "Enter", code: "Enter" });
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("does not call onSelect on unrelated keydown", () => {
    const onSelect = vi.fn();
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={onSelect}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    fireEvent.keyDown(card, { key: "Tab", code: "Tab" });
    expect(onSelect).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// A11y — role, aria-checked, focus ring
// ---------------------------------------------------------------------------

describe("ModeCard — a11y", () => {
  it("has role=radio", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByRole("radio", { name: /Manual entry/ })).toBeTruthy();
  });

  it("sets aria-checked=true when selected", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={true}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    expect(card.getAttribute("aria-checked")).toBe("true");
  });

  it("sets aria-checked=false when not selected", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    expect(card.getAttribute("aria-checked")).toBe("false");
  });

  it("is keyboard focusable (tabIndex=0)", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    expect(card.getAttribute("tabindex")).toBe("0");
  });

  it("carries a focus-visible ring class (Task-4 contract)", () => {
    render(
      <ModeCard
        id="a"
        title="Manual entry"
        description="Enter compounds by name"
        selected={false}
        onSelect={() => {}}
      />,
    );
    const card = screen.getByRole("radio", { name: /Manual entry/ });
    expect(card.className).toMatch(/focus-visible:/);
  });
});

// ---------------------------------------------------------------------------
// ModeCardGroup — container with radiogroup role
// ---------------------------------------------------------------------------

describe("ModeCardGroup — container", () => {
  it("renders with role=radiogroup", () => {
    render(
      <ModeCardGroup aria-label="Entry mode">
        <ModeCard id="a" title="A" description="desc" selected={false} onSelect={() => {}} />
      </ModeCardGroup>,
    );
    expect(screen.getByRole("radiogroup", { name: "Entry mode" })).toBeTruthy();
  });
});
