import { expect, test, vi } from "vitest";
import { jumpToLine } from "./jump-to-line";

const TEXT = "abc\nde\nfghij";
// line 1 starts at offset 0  (length 3)
// line 2 starts at offset 4  (3 + 1 newline)
// line 3 starts at offset 7  (3 + 1 + 2 + 1)

test("no-ops when el is null", () => {
  // should not throw
  jumpToLine(null, TEXT, 1);
});

test("jumps to the start of line 1 (offset 0)", () => {
  const el = {
    focus: vi.fn(),
    setSelectionRange: vi.fn(),
  } as unknown as HTMLTextAreaElement;
  jumpToLine(el, TEXT, 1);
  expect(el.setSelectionRange).toHaveBeenCalledWith(0, 0);
});

test("jumps to the start of line 2 (offset 4)", () => {
  const el = {
    focus: vi.fn(),
    setSelectionRange: vi.fn(),
  } as unknown as HTMLTextAreaElement;
  jumpToLine(el, TEXT, 2);
  expect(el.setSelectionRange).toHaveBeenCalledWith(4, 4);
});

test("jumps to the start of line 3 (offset 7)", () => {
  const el = {
    focus: vi.fn(),
    setSelectionRange: vi.fn(),
  } as unknown as HTMLTextAreaElement;
  jumpToLine(el, TEXT, 3);
  expect(el.setSelectionRange).toHaveBeenCalledWith(7, 7);
});

test("swallows errors thrown by setSelectionRange", () => {
  const el = {
    focus: vi.fn(),
    setSelectionRange: vi.fn().mockImplementation(() => {
      throw new Error("not supported");
    }),
  } as unknown as HTMLTextAreaElement;
  // should not throw
  jumpToLine(el, TEXT, 1);
});
