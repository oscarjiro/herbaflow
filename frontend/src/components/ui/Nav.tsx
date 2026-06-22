import { Link, useMatchRoute } from "@tanstack/react-router";
import { ThemeToggle } from "./ThemeToggle";
import { SHELL_MODE } from "@/lib/shellMode";

const navLink =
  "text-hf-fg-2 hover:text-hf-fg-1 text-xs uppercase tracking-[0.16em] transition-colors";

export function Nav() {
  const matchRoute = useMatchRoute();
  // The run page (/analysis/$id) uses the fixed RunSidebar as its chrome — hide the top nav there.
  if (matchRoute({ to: "/analysis/$id" })) return null;
  // In unified shell mode, the setup route also hides the global nav (SetupShell provides its own chrome).
  if (SHELL_MODE === "unified" && matchRoute({ to: "/analysis" })) return null;

  return (
    <header className="relative z-20">
      <nav className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-5">
        <span className="flex-1" aria-hidden="true" />
        {/* Analysis · logo · About, clustered centrally */}
        <div className="flex items-center gap-10">
          <Link to="/analysis" className={navLink}>
            Analysis
          </Link>
          <Link to="/" aria-label="Herbaflow home" className="text-hf-fg-1">
            <span className="hf-logo block h-9 w-[150px]" />
          </Link>
          <Link to="/about" className={navLink}>
            About
          </Link>
        </div>
        {/* Theme control alone at the far right */}
        <span className="flex flex-1 justify-end">
          <ThemeToggle />
        </span>
      </nav>
    </header>
  );
}
