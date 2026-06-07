import { render, screen } from "@testing-library/react";
import { App } from "../src/App";

test("renders the app name", () => {
  render(<App />);
  expect(screen.getByText("Herbaflow")).toBeInTheDocument();
});
