import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ToasterProps } from "sonner";

// Capture the props the wrapper forwards to the underlying sonner <Toaster>,
// so we can assert the ink-surface classNames + per-status dot icons are wired
// through sonner's documented toastOptions/icons config (not just present in
// the file). The real library is replaced with a spy that records its props.
const sonnerProps = vi.fn<(props: ToasterProps) => void>();

vi.mock("sonner", () => ({
  Toaster: (props: ToasterProps) => {
    sonnerProps(props);
    return null;
  },
}));

import { Toaster } from "./sonner";

function getForwardedProps(): ToasterProps {
  render(<Toaster />);
  expect(sonnerProps).toHaveBeenCalled();
  return sonnerProps.mock.calls.at(-1)![0];
}

describe("Toaster — glass surface + status dot", () => {
  it("forwards a glass toast className through toastOptions", () => {
    const props = getForwardedProps();
    const toastClass = props.toastOptions?.classNames?.toast ?? "";
    // Glass panel: translucent inline-glass surface + normal foreground text.
    expect(toastClass).toContain("hf-glass-panel");
    expect(toastClass).toContain("text-hf-fg-1");
  });

  it("renders the toast unstyled so the glass classNames fully control the look", () => {
    const props = getForwardedProps();
    expect(props.toastOptions?.unstyled).toBe(true);
  });

  it("keeps position bottom-right when not overridden by callers", () => {
    const props = getForwardedProps();
    // Default mount position; __root mounts with position="bottom-right".
    expect(props.position ?? "bottom-right").toBe("bottom-right");
  });

  it.each([
    ["success", "bg-hf-success"],
    ["warning", "bg-hf-warning"],
    ["error", "bg-hf-danger"],
    ["info", "bg-hf-info"],
  ] as const)("uses a %s status dot colored from its status token", (type, dotClass) => {
    const props = getForwardedProps();
    const node = props.icons?.[type];
    const { container } = render(<>{node}</>);
    const dot = container.querySelector(`.${dotClass}`);
    expect(dot).not.toBeNull();
  });

  it("forwards explicit overrides (callers may still set props)", () => {
    sonnerProps.mockClear();
    render(<Toaster position="top-center" />);
    const props = sonnerProps.mock.calls.at(-1)![0];
    expect(props.position).toBe("top-center");
  });
});
