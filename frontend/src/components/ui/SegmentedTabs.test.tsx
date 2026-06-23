import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { SegmentedTabs } from "./SegmentedTabs";

const opts = [
  { value: "selection", label: "Select plants" },
  { value: "manual_compounds", label: "Enter compounds" },
] as const;

function Harness() {
  const [v, setV] = useState("a");
  return (
    <SegmentedTabs
      value={v}
      onChange={setV}
      ariaLabel="demo"
      options={[
        { value: "a", label: "A", description: "Alpha mode." },
        { value: "b", label: "B", description: "Beta mode." },
      ]}
    />
  );
}

test("shows the active option's description and updates on switch", async () => {
  const { container } = render(<Harness />);
  const desc = container.querySelector("[data-slot='segment-description']")!;
  expect(desc.textContent).toBe("Alpha mode.");
  await userEvent.click(screen.getByText("B"));
  expect(container.querySelector("[data-slot='segment-description']")!.textContent).toBe(
    "Beta mode.",
  );
});

test("marks the active segment and switches on click", async () => {
  const user = userEvent.setup();
  const onChange = vi.fn();
  render(
    <SegmentedTabs
      value="selection"
      onChange={onChange}
      options={[...opts]}
      ariaLabel="Plant input mode"
    />,
  );
  const active = screen.getByRole("radio", { name: "Select plants" });
  expect(active).toHaveAttribute("aria-checked", "true");
  await user.click(screen.getByRole("radio", { name: "Enter compounds" }));
  expect(onChange).toHaveBeenCalledWith("manual_compounds");
});
