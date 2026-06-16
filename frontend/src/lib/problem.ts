export type Problem = {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  errors?: { detail?: string; pointer?: string }[];
};

export function humanizeProblem(p: Problem | undefined | null): string {
  if (!p) return "Something went wrong. Please try again.";
  if (p.detail) return p.detail;
  if (p.errors?.length && p.errors[0]?.detail) return p.errors[0].detail ?? "";
  if (p.title) return p.title;
  return "Something went wrong. Please try again.";
}
