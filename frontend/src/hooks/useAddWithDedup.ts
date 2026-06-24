import { useCallback, useState } from "react";

/**
 * Split freshly resolved items into those already in the current stage set vs new,
 * remember the already-present ones for an "N already in run" note, and emit only the
 * new ids to the edit mutation. The single home for the dedup-on-add UX shared by the
 * Stage 1/3/4 add boxes and the STP dialog.
 */
export function useAddWithDedup<T, TContext = undefined>({
  currentIds,
  getId,
  onAddIds,
}: {
  currentIds: Set<string>;
  getId: (item: T) => string;
  onAddIds: (ids: string[], context?: TContext) => void;
}): { alreadyInRun: T[]; handleAdd: (resolved: T[], context?: TContext) => void } {
  const [alreadyInRun, setAlreadyInRun] = useState<T[]>([]);
  const handleAdd = useCallback(
    (resolved: T[], context?: TContext) => {
      const already = resolved.filter((r) => currentIds.has(getId(r)));
      const fresh = resolved.filter((r) => !currentIds.has(getId(r)));
      setAlreadyInRun(already);
      if (context !== undefined) {
        onAddIds(fresh.map(getId), context);
      } else if (fresh.length > 0) {
        onAddIds(fresh.map(getId));
      }
    },
    [currentIds, getId, onAddIds],
  );
  return { alreadyInRun, handleAdd };
}
