import { Link, useMatchRoute } from "@tanstack/react-router";
import { ThemeToggle } from "./ThemeToggle";

export function Nav() {
  const matchRoute = useMatchRoute();
  // The run page (/analysis/$id) uses the fixed RunSidebar as its chrome — hide the top nav there.
  if (matchRoute({ to: "/analysis/$id" })) return null;

  return (
    <header className="border-hf-border bg-hf-bg/80 sticky top-0 z-40 border-b backdrop-blur">
      <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link to="/" className="font-display text-hf-fg-1 text-lg tracking-tight">
          Herbaflow
        </Link>
        <div className="flex items-center gap-6">
          <Link
            to="/analysis"
            className="text-hf-fg-2 hover:text-hf-fg-1 text-sm transition-colors"
          >
            Analysis
          </Link>
          <Link to="/about" className="text-hf-fg-2 hover:text-hf-fg-1 text-sm transition-colors">
            About
          </Link>
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
