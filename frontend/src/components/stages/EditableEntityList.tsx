/**
 * EditableEntityList — Stage 1's editable entity list: rows with a remove control + a cap-aware add
 * box (EntityAddControl). Stage 3/4 use the rich table's own delete column instead. Hides
 * user-removed rows; undo = re-add via the add box.
 *
 * NOTE: the full unification of ALL tables onto the shared table primitive is later design-phase
 * work. This component is the interim Stage-1 editor.
 */
import type React from "react";
import { atMinEntities, isUserRemoved } from "../../lib/entities";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EntityAddControl } from "./EntityAddControl";

export type EditableEntity = {
  id: string;
  label: string;
  tag?: string;
};

export function EditableEntityList({
  entities,
  onRemove,
  cap,
  current,
  addControl,
}: {
  entities: EditableEntity[];
  onRemove: (id: string) => void;
  cap: number;
  current: number;
  addControl?: React.ReactNode;
}) {
  const atMin = atMinEntities(current);
  const visible = entities.filter((e) => !isUserRemoved(e.tag));

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-1.5">
        {visible.map((e) => (
          <li key={e.id} className="flex items-center justify-between gap-2">
            <Badge variant="secondary" className="max-w-xs truncate">
              {e.label}
            </Badge>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={`Remove ${e.label}`}
              onClick={() => onRemove(e.id)}
              disabled={atMin}
              title={atMin ? "A stage must keep at least one entry." : undefined}
            >
              ✕
            </Button>
          </li>
        ))}
      </ul>
      {addControl && (
        <EntityAddControl current={current} cap={cap}>
          {addControl}
        </EntityAddControl>
      )}
    </div>
  );
}
