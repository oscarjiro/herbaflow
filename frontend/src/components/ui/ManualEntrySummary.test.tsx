import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ManualEntrySummary, nonEmptyLineCount } from "./ManualEntrySummary";

test("nonEmptyLineCount ignores blank lines", () => {
  expect(nonEmptyLineCount("a\n\n b \n")).toBe(2);
});

test("renders valid/invalid/duplicate counts and the cap", () => {
  render(
    <ManualEntrySummary
      validCount={3}
      invalidCount={1}
      duplicateCount={2}
      current={6}
      max={2000}
    />,
  );
  expect(screen.getByText(/valid/i)).toBeInTheDocument();
  expect(screen.getByText(/invalid/i)).toBeInTheDocument();
  expect(screen.getByText(/duplicates/i)).toBeInTheDocument();
  expect(screen.getByText("6 / 2,000")).toBeInTheDocument();
});

test("Clear fires onClear", async () => {
  const user = userEvent.setup();
  const onClear = vi.fn();
  render(
    <ManualEntrySummary
      validCount={0}
      invalidCount={0}
      duplicateCount={0}
      current={0}
      max={2000}
      onClear={onClear}
    />,
  );
  await user.click(screen.getByRole("button", { name: /clear/i }));
  expect(onClear).toHaveBeenCalled();
});
