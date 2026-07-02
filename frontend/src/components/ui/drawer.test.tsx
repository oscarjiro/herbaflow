import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "./drawer";

afterEach(() => cleanup());

describe("Drawer", () => {
  it("opens side content from the trigger", () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));

    expect(screen.getByRole("dialog", { name: /navigation/i })).toBeInTheDocument();
    expect(screen.getByText("Drawer body")).toBeInTheDocument();
  });

  it("marks the requested side for responsive positioning", () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));

    expect(screen.getByRole("dialog", { name: /navigation/i })).toHaveAttribute(
      "data-side",
      "left",
    );
  });

  it("closes from the built-in close button", () => {
    renderDrawer();

    fireEvent.click(screen.getByRole("button", { name: /open menu/i }));
    fireEvent.click(screen.getByRole("button", { name: /close drawer/i }));

    expect(screen.queryByRole("dialog", { name: /navigation/i })).not.toBeInTheDocument();
  });
});

function renderDrawer() {
  return render(
    <Drawer>
      <DrawerTrigger>Open menu</DrawerTrigger>
      <DrawerContent side="left">
        <DrawerHeader>
          <DrawerTitle>Navigation</DrawerTitle>
          <DrawerDescription>Responsive navigation</DrawerDescription>
        </DrawerHeader>
        <p>Drawer body</p>
      </DrawerContent>
    </Drawer>,
  );
}
