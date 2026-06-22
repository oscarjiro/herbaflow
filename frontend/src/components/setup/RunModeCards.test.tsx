import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunModeCards } from "./RunModeCards";

test("renders solid selection cards (no glass) with guided selectable", async () => {
  const onChange = vi.fn();
  const { container } = render(<RunModeCards value="guided" onChange={onChange} />);
  // no glass surface inside the cards
  expect(container.querySelector(".hf-glass")).toBeNull();
  // selected card is marked + shows the filled check
  const selected = container.querySelector("[data-selected='true']")!;
  expect(selected).not.toBeNull();
  expect(selected.querySelector("svg")).not.toBeNull(); // lucide Check tick
  // solid surface class present
  expect(selected.className).toMatch(/bg-hf-surface/);
  await userEvent.click(screen.getByText(/automatic/i));
  expect(onChange).toHaveBeenCalledWith("auto");
});
