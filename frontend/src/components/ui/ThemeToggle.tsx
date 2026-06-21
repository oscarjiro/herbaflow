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
      variant="ghost"
      size="icon"
      aria-label={`Theme: ${pref}. Activate to change.`}
      onClick={() => setPref(NEXT[pref])}
    >
      <AnimatePresence mode="wait" initial={false}>
        <m.span
          key={pref}
          data-motion-reduced={shouldReduceMotion ? "true" : undefined}
          initial={shouldReduceMotion ? false : { rotate: -180, scale: 0.4, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={shouldReduceMotion ? {} : { rotate: 180, scale: 0.4, opacity: 0 }}
          transition={
            shouldReduceMotion
              ? { duration: 0 }
              : { type: "spring", stiffness: 260, damping: 22, duration: 0.42 }
          }
          className="inline-flex"
        >
          <Icon as={ICON[pref]} />
        </m.span>
      </AnimatePresence>
    </Button>
  );
}
