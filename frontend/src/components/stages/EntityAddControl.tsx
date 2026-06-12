import React from "react";

/**
 * Cap-aware add affordance: shows `current / cap` and disables its children when at cap. The single
 * home for the add control, shared by Stage 1's EditableEntityList and the standalone Stage 3/4 add
 * boxes — so the cap logic is never copy-pasted.
 */
export function EntityAddControl({
  current,
  cap,
  children,
}: {
  current: number;
  cap: number;
  children: React.ReactNode;
}) {
  const atCap = current >= cap;
  return (
    <div className="entity-add">
      <p className="hf-caption">
        {current} / {cap}
      </p>
      <div className={`entity-add-control${atCap ? " entity-add-control--disabled" : ""}`}>
        {atCap
          ? React.Children.map(children, (child) =>
              React.isValidElement(child)
                ? React.cloneElement(child as React.ReactElement<{ disabled?: boolean }>, {
                    disabled: true,
                  })
                : child,
            )
          : children}
      </div>
    </div>
  );
}
