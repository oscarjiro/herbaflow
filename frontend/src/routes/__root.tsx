import { createRootRoute, Outlet, useRouterState } from "@tanstack/react-router";
import { LazyMotion, domAnimation, useReducedMotion } from "motion/react";
import { ReactLenis } from "lenis/react";
import { ThemeProvider } from "@/lib/theme";
import { BackgroundFX } from "@/components/ui/BackgroundFX";
import { Nav } from "@/components/ui/Nav";
import { Footer } from "@/components/ui/Footer";
import { Toaster } from "@/components/ui/sonner";
import { PageTransition } from "@/components/motion/PageTransition";
import { SMOOTH_SCROLL_OPTIONS, shouldSmoothScroll } from "@/lib/smoothScroll";

function RootLayout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const reduceMotion = useReducedMotion();
  // Inertial scroll only on the presentational routes, and never under reduced
  // motion. Mounting/unmounting ReactLenis as the route changes restores native
  // scrolling on the analysis pages. See src/lib/smoothScroll.ts.
  const smoothScroll = shouldSmoothScroll(pathname, Boolean(reduceMotion));

  return (
    <ThemeProvider>
      {smoothScroll && <ReactLenis root options={SMOOTH_SCROLL_OPTIONS} />}
      <LazyMotion features={domAnimation}>
        {/*
        #hf-liquid SVG filter — mounted once here so every GlassSurface
        anywhere in the tree can reference it via filter: url(#hf-liquid).
        Visually hidden via position:absolute + 0×0 size (NOT display:none,
        which disables SVG filters in some browser engines).
        feTurbulence → feGaussianBlur → feDisplacementMap = lens refraction.
      */}
        <svg
          aria-hidden="true"
          width="0"
          height="0"
          style={{ position: "absolute", overflow: "hidden" }}
        >
          <defs>
            <filter
              id="hf-liquid"
              x="0%"
              y="0%"
              width="100%"
              height="100%"
              filterUnits="objectBoundingBox"
            >
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.008 0.008"
                numOctaves={2}
                seed={7}
                result="noise"
              />
              <feGaussianBlur in="noise" stdDeviation={2.2} result="soft" />
              <feDisplacementMap
                in="SourceGraphic"
                in2="soft"
                scale={78}
                xChannelSelector="R"
                yChannelSelector="G"
              />
            </filter>
          </defs>
        </svg>
        <div className="bg-hf-bg text-hf-fg-1 flex min-h-dvh flex-col">
          {/* Decorative dotted-glow background, fixed behind all content (z-0). One
              canonical home — every route inherits it; pages must not re-mount it. */}
          <BackgroundFX glow="blobs" />
          <Nav />
          <main className="flex-1">
            <PageTransition>
              <Outlet />
            </PageTransition>
          </main>
          <Footer />
          <Toaster position="bottom-right" />
        </div>
      </LazyMotion>
    </ThemeProvider>
  );
}

export const Route = createRootRoute({
  component: RootLayout,
  errorComponent: ({ error }) => (
    <div className="mx-auto max-w-prose p-8">
      <p className="text-hf-fg-2">{error.message}</p>
    </div>
  ),
});
