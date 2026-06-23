import * as React from "react";

import { cn } from "@/lib/cn";

// Format a number with commas (e.g. 2000 → "2,000")
function fmtNum(n: number): string {
  return n.toLocaleString("en-US");
}

export interface InputProps extends React.ComponentProps<"input"> {
  // When provided, renders an inline "n / max" character cap counter below the input.
  // Display only — does not enforce the limit.
  maxLength?: number;
}

function Input({
  className,
  type,
  maxLength,
  defaultValue,
  value,
  onChange,
  ...props
}: InputProps) {
  const showCap = maxLength !== undefined;

  const initialValue =
    value !== undefined ? String(value) : defaultValue !== undefined ? String(defaultValue) : "";

  const [charCount, setCharCount] = React.useState(initialValue.length);

  // Keep charCount in sync when the controlled value prop changes from outside.
  const isControlled = value !== undefined;
  React.useEffect(() => {
    if (isControlled) {
      setCharCount(String(value ?? "").length);
    }
  }, [value, isControlled]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (showCap) setCharCount(e.target.value.length);
    onChange?.(e);
  }

  const inputEl = (
    <input
      type={type}
      data-slot="input"
      maxLength={maxLength}
      value={value}
      defaultValue={isControlled ? undefined : defaultValue}
      onChange={handleChange}
      className={cn(
        // Surface + border + radius — SOLID (no glass on form controls)
        "bg-hf-surface border-hf-border-strong rounded-sm border",
        // Layout
        "h-9 w-full min-w-0",
        // Typography
        "text-hf-fg-1 text-base md:text-sm",
        "placeholder:text-hf-fg-4",
        // Selection colours
        "selection:bg-primary selection:text-primary-foreground",
        // File input slots
        "file:text-foreground file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        // Spacing
        "px-3 py-1",
        // Suppress default outline (our ink-border rule handles focus)
        "outline-none",
        // Disabled state
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        // Animated ink-border focus: border animates to ink + soft glow; no ring
        "hf-ink-focus",
        // Invalid state — danger border colour (CSS .hf-ink-focus rule handles the rest)
        "aria-invalid:border-hf-danger",
        className,
      )}
      {...props}
    />
  );

  if (!showCap) return inputEl;

  return (
    <div className="relative w-full">
      {inputEl}
      <span
        data-slot="char-cap"
        aria-live="polite"
        className="text-hf-fg-4 pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs tabular-nums select-none"
      >
        {fmtNum(charCount)} / {fmtNum(maxLength!)}
      </span>
    </div>
  );
}

export { Input };
