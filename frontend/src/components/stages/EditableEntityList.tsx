/**
 * EditableEntityList — generic reusable list of entities with remove controls
 * and an optional add affordance.
 *
 * Props:
 *  - entities: array of { id, label, tag? }
 *  - onRemove(id): called when the remove button is clicked
 *  - onAdd?: optional callback when add is triggered (wired externally)
 *  - cap: maximum number of entities allowed
 *  - current: current count (used for cap enforcement display)
 *  - addControl?: optional React node rendered as the add affordance; it will
 *    receive a `disabled` attribute when current >= cap via the wrapper
 *    (for <input> / <button> children the parent should pass disabled
 *    themselves, or use the `addControl` slot only when cap not reached)
 */

import React from "react";

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
  onAdd?: (...args: unknown[]) => void;
  cap: number;
  current: number;
  addControl?: React.ReactNode;
}) {
  const atCap = current >= cap;
  const atMin = current <= 1;

  return (
    <div className="editable-entity-list">
      <p className="hf-caption">
        {current} / {cap}
      </p>
      <ul>
        {entities.map((e) => (
          <li
            key={e.id}
            className={e.tag === "user-removed" ? "entity-row entity-row--removed" : "entity-row"}
          >
            <span className={e.tag === "user-removed" ? "user-removed" : undefined}>{e.label}</span>
            <button
              className="hf-btn hf-btn-icon"
              aria-label={`Remove ${e.label}`}
              onClick={() => onRemove(e.id)}
              disabled={atMin && e.tag !== "user-removed"}
              title={
                atMin && e.tag !== "user-removed"
                  ? "A stage must keep at least one entry."
                  : undefined
              }
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
      {addControl && (
        <div className={`entity-add-control${atCap ? " entity-add-control--disabled" : ""}`}>
          {atCap
            ? React.Children.map(addControl, (child) => {
                if (React.isValidElement(child)) {
                  // Propagate disabled to form elements when at cap
                  return React.cloneElement(child as React.ReactElement<{ disabled?: boolean }>, {
                    disabled: true,
                  });
                }
                return child;
              })
            : addControl}
        </div>
      )}
    </div>
  );
}
