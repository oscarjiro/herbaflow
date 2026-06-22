import { render, screen } from "@testing-library/react";
import type { AnalysisRead } from "@/api/types.gen";
import { RunIdentityCard } from "./RunIdentityCard";

test("shows the custom run name, never the UUID", () => {
  const data = {
    analysis_id: "11111111-2222-3333-4444-555555555555",
    analysis_name: "Curcuma vs T2DM",
    mode: "guided",
    created_at: new Date().toISOString(),
  } as AnalysisRead;
  render(<RunIdentityCard data={data} />);
  expect(screen.getByText("Curcuma vs T2DM")).toBeInTheDocument();
  expect(screen.queryByText(/11111111-2222/)).toBeNull();
  expect(screen.getByText(/guided/i)).toBeInTheDocument();
});
