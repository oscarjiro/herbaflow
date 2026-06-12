/** "N already in run: a, b, c" status note shown after a no-op/partial add. */
export function AlreadyInRunNote({ labels }: { labels: string[] }) {
  if (labels.length === 0) return null;
  return (
    <p className="hf-muted" role="status">
      {labels.length} already in run: {labels.join(", ")}
    </p>
  );
}
