import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SegmentedTabs } from "./SegmentedTabs";

const opts = [
  { value: "selection", label: "Select plants" },
  { value: "manual_compounds", label: "Enter compounds" },
] as const;

test("marks the active segment and switches on click", async () => {
  const user = userEvent.setup();
  const onChange = vi.fn();
  render(
    <SegmentedTabs value="selection" onChange={onChange} options={[...opts]} ariaLabel="Plant input mode" />,
  );
  const active = screen.getByRole("radio", { name: "Select plants" });
  expect(active).toHaveAttribute("aria-checked", "true");
  await user.click(screen.getByRole("radio", { name: "Enter compounds" }));
  expect(onChange).toHaveBeenCalledWith("manual_compounds");
});
