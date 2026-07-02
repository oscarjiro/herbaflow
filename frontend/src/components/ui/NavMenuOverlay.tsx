import { Link } from "@tanstack/react-router";
import { Dialog as DialogPrimitive } from "radix-ui";
import { HamburgerIcon } from "./HamburgerIcon";
import { navLinkBase } from "./Nav";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Full-screen blurred nav menu. The backdrop is a plain, light translucent frost
 * matching the run top bar (`bg-hf-bg` at a low opacity + `backdrop-blur-xl`) —
 * no refraction lens. Enter/exit is a plain opacity fade (`.hf-anim-fade`); Radix
 * holds the node mounted through the close animation. The burger stays pinned
 * top-left in its open (X) state as the close affordance, so it never appears to
 * vanish. Clicking anywhere — including a nav link — closes it; the theme toggle
 * stops propagation so cycling the theme keeps the menu open.
 */
export function NavMenuOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="hf-anim-fade bg-hf-bg/25 supports-[backdrop-filter]:bg-hf-bg/12 fixed inset-0 z-40 backdrop-blur-xl backdrop-saturate-150" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          onClick={onClose}
          className="hf-anim-fade fixed inset-0 z-50 outline-none"
        >
          <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>

          {/* Burger stays top-left as the open (X) close affordance. */}
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={onClose}
            className="hf-ink-focus text-hf-fg-1 absolute top-4 left-4 z-10 -m-2 inline-flex items-center justify-center rounded-md p-2 sm:top-5 sm:left-6"
          >
            <HamburgerIcon open />
          </button>

          <div className="relative z-10 flex h-full flex-col items-center justify-center gap-8">
            <Link to="/" aria-label="Herbaflow home" onClick={onClose} className="text-hf-fg-1">
              <span className="hf-logo block h-9 w-[150px]" aria-hidden="true" />
            </Link>
            <Link to="/analysis" onClick={onClose} className={`${navLinkBase} text-base`}>
              Analysis
            </Link>
            <Link to="/about" onClick={onClose} className={`${navLinkBase} text-base`}>
              About
            </Link>
            <span onClick={(e) => e.stopPropagation()}>
              <ThemeToggle />
            </span>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
