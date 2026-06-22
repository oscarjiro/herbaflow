import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunModeCards } from "./RunModeCards";

test("shows both modes, marks the selected one, and switches", async () => {
  const user = userEvent.setup();
  const onChange = vi.fn();
  render(<RunModeCards value="guided" onChange={onChange} />);
  const guided = screen.getByRole("radio", { name: /guided/i });
  const auto = screen.getByRole("radio", { name: /automatic/i });
  expect(guided).toHaveAttribute("aria-checked", "true");
  expect(auto).toHaveAttribute("aria-checked", "false");
  await user.click(auto);
  expect(onChange).toHaveBeenCalledWith("auto");
});
