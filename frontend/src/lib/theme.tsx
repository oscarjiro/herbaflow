import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type ThemePref = "system" | "light" | "dark";
type Resolved = "light" | "dark";
type Ctx = {
  pref: ThemePref;
  resolved: Resolved;
  /** Back-compat alias of `resolved` (used by chartTheme). */
  theme: Resolved;
  setPref: (p: ThemePref) => void;
  /** Back-compat: flip the resolved theme by setting an explicit pref. */
  toggle: () => void;
};

const ThemeContext = createContext<Ctx | null>(null);
const STORAGE_KEY = "hf-theme";

function prefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function initialPref(): ThemePref {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") return stored;
  return "system"; // default = follow the OS
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(initialPref);
  const [systemIsDark, setSystemIsDark] = useState<boolean>(prefersDark);

  // Live OS tracking only while following the system preference.
  useEffect(() => {
    if (pref !== "system") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => setSystemIsDark(e.matches);
    setSystemIsDark(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [pref]);

  const resolved: Resolved = pref === "system" ? (systemIsDark ? "dark" : "light") : pref;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark");
    localStorage.setItem(STORAGE_KEY, pref);
  }, [resolved, pref]);

  const setPref = (p: ThemePref) => setPrefState(p);
  const toggle = () => setPrefState(resolved === "dark" ? "light" : "dark");

  return (
    <ThemeContext.Provider value={{ pref, resolved, theme: resolved, setPref, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
