import { render, screen } from "@testing-library/react";
import { StatCards } from "./StatCards";

test("StatCards renders the three stat numbers", () => {
  render(<StatCards />);
  expect(screen.getByText("478")).toBeInTheDocument();
  expect(screen.getByText("11,307")).toBeInTheDocument();
  expect(screen.getByText("10")).toBeInTheDocument();
});

test("StatCards renders the plant count label and sub-label", () => {
  render(<StatCards />);
  expect(screen.getByText(/Indonesian medicinal plants/i)).toBeInTheDocument();
  expect(screen.getByText(/Ethnobotanically used, literature-curated/i)).toBeInTheDocument();
});

test("StatCards renders the compound count label and sub-label", () => {
  render(<StatCards />);
  expect(screen.getByText(/Bioactive compounds/i)).toBeInTheDocument();
  expect(screen.getByText(/Plant metabolites from KNApSAcK/i)).toBeInTheDocument();
});

test("StatCards renders the disease count label and sub-label", () => {
  render(<StatCards />);
  expect(screen.getByText(/Curated diseases/i)).toBeInTheDocument();
  expect(screen.getByText(/Well-studied and clinically relevant/i)).toBeInTheDocument();
});
