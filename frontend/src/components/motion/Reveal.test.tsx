import { render, screen } from "@testing-library/react";
import { LazyMotion, domAnimation } from "motion/react";
import { Reveal } from "./Reveal";

test("Reveal renders its children", () => {
  render(
    <LazyMotion features={domAnimation}>
      <Reveal>
        <p>revealed content</p>
      </Reveal>
    </LazyMotion>,
  );

  expect(screen.getByText("revealed content")).toBeInTheDocument();
});

test("Reveal forwards a className to its wrapper", () => {
  const { container } = render(
    <LazyMotion features={domAnimation}>
      <Reveal className="ab-reveal-x">
        <span>x</span>
      </Reveal>
    </LazyMotion>,
  );

  expect(container.querySelector(".ab-reveal-x")).toBeInTheDocument();
});
