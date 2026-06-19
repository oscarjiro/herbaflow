import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/about")({
  component: AboutPage,
});

function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <h1 className="font-display text-hf-fg-1 mb-6 text-3xl tracking-tight">
        About Herbaflow
      </h1>
      <p className="text-hf-fg-2 mb-4 leading-relaxed">
        Herbaflow is a network pharmacology platform for Indonesian medicinal
        plants. It maps relationships between plants, their bioactive compounds,
        protein targets, and disease associations, drawing on curated
        phytochemical databases and public bioactivity repositories.
      </p>
      <p className="text-hf-fg-2 leading-relaxed">
        Given a set of plants (or compounds and targets supplied directly), the
        platform runs a multi-step analysis pipeline: it resolves compounds,
        filters them by drug-likeness criteria, identifies protein targets,
        overlaps those targets with disease-associated proteins, reconstructs a
        protein interaction network among the shared targets, ranks hub genes by
        network centrality, and performs gene-set enrichment analysis to
        characterize the biological processes involved.
      </p>
    </div>
  );
}
