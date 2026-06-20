import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { LineNumberedTextarea } from "./line-numbered-textarea";

function getGutter(): HTMLElement {
  return screen.getByTestId("line-gutter");
}

function getGutterSpans(): Element[] {
  return Array.from(getGutter().querySelectorAll("span"));
}

test("renders one gutter line-number span per line of value", () => {
  render(<LineNumberedTextarea value={"alpha\nbeta\ngamma"} onChange={() => {}} />);
  const spans = getGutterSpans();
  expect(spans).toHaveLength(3);
  expect(spans[0]?.textContent).toBe("1");
  expect(spans[1]?.textContent).toBe("2");
  expect(spans[2]?.textContent).toBe("3");
});

test("renders one gutter span even for empty value", () => {
  render(<LineNumberedTextarea value={""} onChange={() => {}} />);
  const spans = getGutterSpans();
  expect(spans).toHaveLength(1);
  expect(spans[0]?.textContent).toBe("1");
});

test("calls onChange with the new value when the user types", async () => {
  const onChange = vi.fn();
  render(<LineNumberedTextarea value={""} onChange={onChange} aria-label="Test editor" />);
  const textarea = screen.getByRole("textbox", { name: "Test editor" });
  await userEvent.type(textarea, "hello");
  expect(onChange).toHaveBeenCalled();
  expect(onChange.mock.calls.some((args) => String(args[0]).includes("h"))).toBe(true);
});

test("marks an errored line in the gutter with ! and a title", () => {
  const errorLines: ReadonlyMap<number, string> = new Map([[2, "not found"]]);
  render(
    <LineNumberedTextarea
      value={"line1\nline2\nline3"}
      onChange={() => {}}
      errorLines={errorLines}
    />,
  );
  const spans = getGutterSpans();

  // Line 1: normal — shows "1", no title
  expect(spans[0]?.textContent).toBe("1");
  expect(spans[0]?.getAttribute("title")).toBeNull();

  // Line 2: errored — shows "!", title = reason
  expect(spans[1]?.textContent).toBe("!");
  expect(spans[1]?.getAttribute("title")).toBe("not found");

  // Line 3: normal — shows "3", no title
  expect(spans[2]?.textContent).toBe("3");
  expect(spans[2]?.getAttribute("title")).toBeNull();
});

test("non-errored lines have no title attribute", () => {
  const errorLines: ReadonlyMap<number, string> = new Map([[1, "bad input"]]);
  render(<LineNumberedTextarea value={"bad\ngood"} onChange={() => {}} errorLines={errorLines} />);
  const spans = getGutterSpans();
  // Line 1 errored
  expect(spans[0]?.getAttribute("title")).toBe("bad input");
  // Line 2 not errored
  expect(spans[1]?.getAttribute("title")).toBeNull();
});

test("disabled prop disables the textarea", () => {
  render(
    <LineNumberedTextarea value={""} onChange={() => {}} disabled aria-label="Disabled editor" />,
  );
  const textarea = screen.getByRole("textbox", { name: "Disabled editor" });
  expect(textarea).toBeDisabled();
});
