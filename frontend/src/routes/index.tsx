import { createFileRoute } from "@tanstack/react-router";
import { BackgroundFX } from "@/components/ui/BackgroundFX";
import { LandingHero } from "@/features/landing/LandingHero";
import { Hero } from "@/features/landing/Hero";
import { StatCards } from "@/features/landing/StatCards";
import { WorkflowTimeline } from "@/features/landing/WorkflowTimeline";
import { DataSources } from "@/features/landing/DataSources";

export const Route = createFileRoute("/")({
  component: LandingPage,
});

function LandingPage() {
  // The app shell (__root) already provides <main>, <Nav>, and <Footer>. This route
  // renders only the background layers + the page sections — no nested <main>.
  return (
    <>
      {/* Fixed, full-viewport decorative layers behind the content. */}
      <BackgroundFX glow="blobs" />
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
