import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RemovableChipList } from "./RemovableChipList";

test("renders hf-token chips and removes on click", async () => {
  const onRemove = vi.fn();
  const { container } = render(
    <RemovableChipList
      items={[{ id: "x", name: "CURCUMIN" }]}
      getKey={(i) => i.id}
      getLabel={(i) => i.name}
      onRemove={onRemove}
      ariaLabel="compounds"
    />,
  );
  // Classes live on the <span> inside <li>
  const chip = container.querySelector("li span")!;
  expect(chip.className).toMatch(/font-mono/);
  expect(chip.className).toMatch(/border-hf-border-strong/);
  expect(chip.className).not.toMatch(/bg-accent\b/);
  await userEvent.click(screen.getByRole("button"));
  expect(onRemove).toHaveBeenCalled();
});
