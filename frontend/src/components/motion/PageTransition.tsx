import type { ReactNode } from "react";
import { useRouterState } from "@tanstack/react-router";
import { m, useReducedMotion } from "motion/react";

/**
 * sectionKey — the top-level route segment, used as the transition's remount key.
 *
 * Navigating between sections (Landing "/", About "/about", Analysis "/analysis")
 * changes the key, so the content remounts and fades in. Navigating WITHIN a section
 * (e.g. stage to stage inside a run, "/analysis/$id/$stage") keeps the same key, so
 * the live run view is not remounted (no polling re-subscribe) on every stage click.
 */
export function sectionKey(pathname: string): string {
  return "/" + (pathname.split("/")[1] ?? "");
}

/**
 * PageTransition — a simple cross-page fade, scoped to the routed content.
 *
 * Wraps the router <Outlet/> so only page content fades; the persistent Nav, Footer,
 * and BackgroundFX stay put. Respects reduced motion (renders a plain wrapper then).
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const reduce = useReducedMotion();
  const key = sectionKey(pathname);

  if (reduce) {
    return <div>{children}</div>;
  }

  return (
    <m.div
      key={key}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25, ease: [0.2, 0.7, 0.2, 1] }}
    >
      {children}
    </m.div>
  );
}
