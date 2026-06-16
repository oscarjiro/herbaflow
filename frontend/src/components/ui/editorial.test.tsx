import { render, screen } from "@testing-library/react";
import { Eyebrow, Binomial } from "./editorial";

test("editorial primitives render content", () => {
  render(
    <>
      <Eyebrow>STEP 1</Eyebrow>
      <Binomial>Curcuma longa</Binomial>
    </>,
  );
  expect(screen.getByText("STEP 1")).toBeInTheDocument();
  expect(screen.getByText("Curcuma longa")).toBeInTheDocument();
});
