import { type RowData } from "@tanstack/react-table";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    /** Tooltip text shown via the circle-i affordance in the column header. */
    info?: string;
    /** Extra CSS classes applied to header <th> and body <td> cells (e.g. "num"). */
    className?: string;
    /** Whether this column supports a per-column filter input (reserved for a later task). */
    filterable?: boolean;
  }
}
