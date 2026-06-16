import { Button } from "@/components/ui/button";
import { useCsvBlobUrl } from "@/lib/csv";

export function CsvDownloadButton({
  header,
  rows,
  filename,
  label = "Download CSV",
}: {
  header: string;
  rows: readonly unknown[][];
  filename: string;
  label?: string;
}) {
  const url = useCsvBlobUrl(header, rows);
  return (
    <Button asChild variant="outline" size="sm">
      <a href={url} download={filename}>
        {label}
      </a>
    </Button>
  );
}
