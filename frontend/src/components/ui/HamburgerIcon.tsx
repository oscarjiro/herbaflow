import { cn } from "@/lib/cn";

/**
 * Plain animated burger — two lines that retract and pivot into an X.
 * Colour comes from `currentColor` (themes via hf tokens); the motion lives
 * in the `.hf-burger` recipe + keyframes in index.css.
 */
export function HamburgerIcon({ open, className }: { open: boolean; className?: string }) {
  return (
    <svg
      className={cn("hf-burger", className)}
      data-state={open ? "open" : "closed"}
      viewBox="0 0 100 100"
      width="28"
      height="28"
      fill="none"
      aria-hidden="true"
    >
      <line
        className="hf-burger__line hf-burger__top"
        x1="90"
        x2="10"
        y1="40"
        y2="40"
        stroke="currentColor"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray="80"
        strokeDashoffset="0"
      />
      <line
        className="hf-burger__line hf-burger__bottom"
        x1="10"
        x2="90"
        y1="60"
        y2="60"
        stroke="currentColor"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray="80"
        strokeDashoffset="0"
      />
    </svg>
  );
}
