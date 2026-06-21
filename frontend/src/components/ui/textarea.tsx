import * as React from "react";

import { cn } from "@/lib/cn";

// Format a number with commas (e.g. 2000 → "2,000")
function fmtNum(n: number): string {
  return n.toLocaleString("en-US");
}

export interface TextareaProps extends React.ComponentProps<"textarea"> {
  // When provided, renders an inline "n / max" character cap counter.
  // Display only — does not enforce the limit.
  maxLength?: number;
}

function Textarea({
  className,
  maxLength,
  defaultValue,
  value,
  onChange,
  ...props
}: TextareaProps) {
  const showCap = maxLength !== undefined;

  const initialValue =
    value !== undefined ? String(value) : defaultValue !== undefined ? String(defaultValue) : "";

  const [charCount, setCharCount] = React.useState(initialValue.length);

  const isControlled = value !== undefined;
  React.useEffect(() => {
    if (isControlled) {
      setCharCount(String(value ?? "").length);
    }
  }, [value, isControlled]);

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    if (showCap) setCharCount(e.target.value.length);
    onChange?.(e);
  }

  const taEl = (
    <textarea
      data-slot="textarea"
      maxLength={maxLength}
      value={value}
      defaultValue={isControlled ? undefined : defaultValue}
      onChange={handleChange}
      className={cn(
        // Surface + border + radius — SOLID (no glass on form controls)
        "bg-hf-surface border-hf-border-strong rounded-sm border",
        // Layout
        "flex field-sizing-content min-h-16 w-full",
        // Typography
        "text-hf-fg-1 text-base md:text-sm",
        "placeholder:text-hf-fg-4",
        // Spacing
        "px-3 py-2",
        // Suppress default outline (ink-border rule handles focus)
        "outline-none",
        // Disabled
        "disabled:cursor-not-allowed disabled:opacity-50",
        // Animated ink-border focus (Task 6): no ring, border animates to ink + soft glow
        "hf-ink-focus",
        // Invalid state
        "aria-invalid:border-hf-danger",
        className,
      )}
      {...props}
    />
  );

  if (!showCap) return taEl;

  return (
    <div className="relative w-full">
      {taEl}
      <span
        data-slot="char-cap"
        aria-live="polite"
        className="text-hf-fg-4 pointer-events-none absolute right-2 bottom-2 text-xs tabular-nums select-none"
      >
        {fmtNum(charCount)} / {fmtNum(maxLength!)}
      </span>
    </div>
  );
}

export { Textarea };
