import { createFileRoute } from "@tanstack/react-router";
import { LandingHero } from "@/features/landing/LandingHero";
import { Hero } from "@/features/landing/Hero";
import { StatCards } from "@/features/landing/StatCards";
import { WorkflowTimeline } from "@/features/landing/WorkflowTimeline";
import { DataSources } from "@/features/landing/DataSources";

export const Route = createFileRoute("/")({
  component: LandingPage,
});

function LandingPage() {
  // The app shell (__root) provides <main>, <Nav>, <Footer>, and the BackgroundFX
  // dotted-glow layer. This route renders only the page sections — no nested <main>,
  // no background (inherited from the root layout).
  return (
    <>
      <LandingHero />
      <div className="relative z-10 mx-auto max-w-6xl px-4">
        <Hero />
        <StatCards className="mt-8" />
        <WorkflowTimeline />
        <DataSources />
      </div>
    </>
  );
}
