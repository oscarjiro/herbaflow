import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";

export function ServiceUnavailable({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center"
    >
      <h1 className="text-2xl font-semibold tracking-tight">Service unavailable</h1>
      <p className="text-hf-fg-2">
        Herbaflow can&apos;t reach its database right now. Please try again in a moment.
      </p>
      <div className="flex items-center gap-3">
        <Button onClick={onRetry}>Retry</Button>
        <Button variant="outline" asChild>
          <Link to="/">Back to landing</Link>
        </Button>
      </div>
    </div>
  );
}
