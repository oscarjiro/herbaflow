import { Badge } from "@/components/ui/badge";

/**
 * The one home for the "Provided by you" badge shown on user-provided entity stages
 * (Stage 1/2/3/4). Renders nothing unless `show` is true.
 */
export function ProvidedByYouBadge({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div>
      <Badge variant="secondary">Provided by you</Badge>
    </div>
  );
}
