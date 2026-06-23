import { render } from "@testing-library/react";
import { FieldCap } from "./FieldCap";

test("renders a localized mono cap badge", () => {
  const { container } = render(<FieldCap current={1200} max={2000} unit="compounds" />);
  const cap = container.querySelector("[data-slot='field-cap']")!;
  expect(cap.textContent).toMatch(/1,200\s*\/\s*2,000/);
  expect(cap.className).toMatch(/font-mono/);
  expect(cap.className).toMatch(/text-hf-fg-4/);
});
