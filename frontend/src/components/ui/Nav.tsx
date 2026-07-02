import { Link, useMatchRoute } from "@tanstack/react-router";
import { useState } from "react";
import { HamburgerIcon } from "./HamburgerIcon";
import { NavMenuOverlay } from "./NavMenuOverlay";
import { ThemeToggle } from "./ThemeToggle";

// Shared nav-link style (size-free) so the desktop bar and the mobile overlay
// use the same all-caps editorial treatment; each call site adds its own size.
export const navLinkBase =
  "text-hf-fg-2 hover:text-hf-fg-1 uppercase tracking-[0.16em] transition-colors";

export function Nav() {
  const matchRoute = useMatchRoute();
  const [open, setOpen] = useState(false);
  // The run page (/analysis/$id and its per-stage children) uses the fixed
  // RunSidebar as its chrome — hide the top nav there. Fuzzy so the /$stage and
  // /inputs child routes match too. The setup route (/analysis) keeps the nav.
  if (matchRoute({ to: "/analysis/$id", fuzzy: true })) return null;

  return (
    <header className="relative z-20">
      <nav className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-4 sm:px-6 sm:py-5">
        <div className="flex flex-1 justify-start md:hidden">
          <button
            type="button"
            aria-label="Open navigation menu"
            onClick={() => setOpen(true)}
            className="hf-ink-focus text-hf-fg-1 -m-2 inline-flex items-center justify-center rounded-md p-2"
          >
            <HamburgerIcon open={open} />
          </button>
        </div>

        <span className="hidden flex-1 md:block" aria-hidden="true" />

        <div className="flex items-center justify-center gap-10">
          <Link to="/analysis" className={`${navLinkBase} hidden text-xs md:inline-flex`}>
            Analysis
          </Link>
          <Link to="/" aria-label="Herbaflow home" className="text-hf-fg-1">
            <span className="hf-logo block h-7 w-[118px] sm:h-8 sm:w-[132px] md:h-9 md:w-[150px]" />
          </Link>
          <Link to="/about" className={`${navLinkBase} hidden text-xs md:inline-flex`}>
            About
          </Link>
        </div>

        <span className="flex flex-1 justify-end">
          <span className="hidden md:block">
            <ThemeToggle />
          </span>
        </span>
      </nav>

      <NavMenuOverlay open={open} onClose={() => setOpen(false)} />
    </header>
  );
}
