import type { ZodType } from "zod";

export type LineError = { line: number; message: string };

export function lineErrorsFor(lines: string[], schema: ZodType): LineError[] {
  const out: LineError[] = [];
  lines.forEach((value, i) => {
    const r = schema.safeParse(value);
    if (!r.success) out.push({ line: i + 1, message: r.error.issues[0]?.message ?? "invalid" });
  });
  return out;
}
