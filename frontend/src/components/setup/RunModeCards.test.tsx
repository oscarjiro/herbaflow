import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunModeCards } from "./RunModeCards";

test("renders glass selection cards with guided selected", async () => {
  const onChange = vi.fn();
  const { container } = render(<RunModeCards value="guided" onChange={onChange} />);
  // selection surfaces use the inline glass treatment (D1)
  expect(container.querySelector(".hf-glass-panel")).not.toBeNull();
  // selected card is marked, aria-checked, and shows the filled check
  const selected = container.querySelector("[data-selected='true']")!;
  expect(selected).not.toBeNull();
  expect(selected).toHaveAttribute("aria-checked", "true");
  expect(selected.querySelector("svg")).not.toBeNull(); // lucide Check tick
  // the other card is an unchecked radio
  const radios = Array.from(container.querySelectorAll("[role='radio']"));
  expect(radios.some((r) => r.getAttribute("aria-checked") === "false")).toBe(true);
  await userEvent.click(screen.getByText(/automatic/i));
  expect(onChange).toHaveBeenCalledWith("auto");
});
