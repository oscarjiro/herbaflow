import { Link } from "@tanstack/react-router";
import { ThemeToggle } from "./ThemeToggle";

export function Nav() {
  return (
    <header className="border-hf-border border-b">
      <nav className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link to="/analysis" className="font-display text-hf-fg-1 text-lg tracking-tight">
          Herbaflow
        </Link>
        <ThemeToggle />
      </nav>
    </header>
  );
}
