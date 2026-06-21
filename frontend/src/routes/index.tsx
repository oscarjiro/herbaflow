import { createFileRoute } from "@tanstack/react-router";
import { Hero } from "@/features/landing/Hero";
import { StatCards } from "@/features/landing/StatCards";

export const Route = createFileRoute("/")({
  component: LandingPage,
});

function LandingPage() {
  return (
    <main className="mx-auto max-w-6xl px-4">
      <Hero />
      <StatCards className="mt-8" />
    </main>
  );
}
