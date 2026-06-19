import { createFileRoute, Link } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: LandingPage,
});

function LandingPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center px-4 py-24 text-center">
      <h1 className="font-display text-hf-fg-1 mb-3 text-4xl tracking-tight">
        Herbaflow
      </h1>
      <p className="text-hf-fg-2 mb-10 text-lg leading-relaxed">
        Network pharmacology for Indonesian medicinal plants. Map compounds,
        targets, and disease associations in one pipeline.
      </p>
      <Link
        to="/analysis"
        className="bg-hf-fg-1 text-hf-bg hover:bg-hf-fg-2 mb-4 rounded-md px-6 py-2.5 text-sm font-medium transition-colors"
      >
        Start an analysis
      </Link>
      <Link
        to="/about"
        className="text-hf-fg-3 hover:text-hf-fg-2 text-sm transition-colors"
      >
        Learn more
      </Link>
    </div>
  );
}
