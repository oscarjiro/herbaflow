import { render, screen } from "@testing-library/react";
import { CsvDownloadButton } from "./CsvDownloadButton";

test("renders a download anchor with the filename and label", () => {
  render(
    <CsvDownloadButton
      header="gene,score"
      rows={[["EGFR", 0.91]]}
      filename="targets.csv"
      label="Download CSV"
    />,
  );
  const link = screen.getByRole("link", { name: "Download CSV" });
  expect(link).toHaveAttribute("download", "targets.csv");
  expect(link).toHaveAttribute("href"); // blob: URL from useCsvBlobUrl (jsdom URL.createObjectURL is stubbed in tests/setup.ts)
});
