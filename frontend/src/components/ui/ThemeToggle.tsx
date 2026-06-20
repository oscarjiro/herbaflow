import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { Icon } from "./Icon";

const NEXT = { system: "light", light: "dark", dark: "system" } as const;
const ICON = { system: Monitor, light: Sun, dark: Moon } as const;

export function ThemeToggle() {
  const { pref, setPref } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`Theme: ${pref}. Activate to change.`}
      onClick={() => setPref(NEXT[pref])}
    >
      <Icon as={ICON[pref]} />
    </Button>
  );
}
