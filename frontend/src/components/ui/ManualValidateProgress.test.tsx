import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { ManualValidateProgress } from "./ManualValidateProgress";

test("has role=status and aria-busy=true", () => {
  render(<ManualValidateProgress kind="compound" entryCount={3} />);
  const status = screen.getByRole("status");
  expect(status).toHaveAttribute("aria-busy", "true");
});

test("label contains count and Validating for compound entries (plural)", () => {
  render(<ManualValidateProgress kind="compound" entryCount={3} />);
  expect(screen.getByRole("status")).toHaveTextContent(/Validating 3 compound entries/i);
});

test("uses singular 'entry' when count is 1", () => {
  render(<ManualValidateProgress kind="target" entryCount={1} />);
  expect(screen.getByRole("status")).toHaveTextContent(/1 target entry/i);
  expect(screen.getByRole("status")).not.toHaveTextContent(/entries/i);
});

test("uses plural 'entries' when count is greater than 1", () => {
  render(<ManualValidateProgress kind="compound" entryCount={5} />);
  expect(screen.getByRole("status")).toHaveTextContent(/5 compound entries/i);
});

test("does not show a slash-separated fraction", () => {
  render(<ManualValidateProgress kind="compound" entryCount={3} />);
  expect(screen.getByRole("status")).not.toHaveTextContent(/\d+\/\d+/);
});

test("does not render a progressbar role", () => {
  render(<ManualValidateProgress kind="target" entryCount={2} />);
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
});
