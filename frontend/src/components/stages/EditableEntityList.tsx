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
    <div className="editable-entity-list">
      <ul>
        {visible.map((e) => (
          <li key={e.id} className="entity-row">
            <span>{e.label}</span>
            <button
              className="hf-btn hf-btn-icon"
              aria-label={`Remove ${e.label}`}
              onClick={() => onRemove(e.id)}
              disabled={atMin}
              title={atMin ? "A stage must keep at least one entry." : undefined}
            >
              ✕
            </button>
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
