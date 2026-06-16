import { z } from "zod";
import { lineErrorsFor } from "./validation";

const smiles = z
  .string()
  .min(1, "empty")
  .regex(/^[^ ]+$/, "no spaces");

test("returns { line, message } for each invalid line", () => {
  const errs = lineErrorsFor(["CCO", "", "C C"], smiles);
  expect(errs).toEqual([
    { line: 2, message: "empty" },
    { line: 3, message: "no spaces" },
  ]);
});
