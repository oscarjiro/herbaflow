import { Monitor, Moon, Sun } from "lucide-react";
import { AnimatePresence, m, useReducedMotion } from "motion/react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { Icon } from "./Icon";

const NEXT = { system: "light", light: "dark", dark: "system" } as const;
const ICON = { system: Monitor, light: Sun, dark: Moon } as const;

export function ThemeToggle() {
  const { pref, setPref } = useTheme();
  const shouldReduceMotion = useReducedMotion();

  return (
    <Button
      variant="glass-action"
      size="icon-lg"
      aria-label={`Theme: ${pref}. Activate to change.`}
      onClick={() => setPref(NEXT[pref])}
    >
      <AnimatePresence mode="wait" initial={false}>
        <m.span
          key={pref}
          data-motion-reduced={shouldReduceMotion ? "true" : undefined}
          initial={shouldReduceMotion ? false : { rotate: -180, scale: 0.4, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          // Mockup hard-swaps the icon (no out-spin); a quick fade stands in so
          // mode="wait" doesn't double the perceived time.
          exit={shouldReduceMotion ? {} : { opacity: 0, transition: { duration: 0.12 } }}
          transition={
            shouldReduceMotion
              ? { duration: 0 }
              : // mockup .theme-btn icon-in: 0.42s tween, ease cubic-bezier(0.2,0.7,0.2,1)
                { duration: 0.42, ease: [0.2, 0.7, 0.2, 1] as [number, number, number, number] }
          }
          className="inline-flex"
        >
          <Icon as={ICON[pref]} className="size-[17px]" />
        </m.span>
      </AnimatePresence>
    </Button>
  );
}
