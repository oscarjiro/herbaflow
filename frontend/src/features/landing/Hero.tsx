import { ArrowRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export function Hero({ className }: { className?: string }) {
  return (
    <section className={cn("flex flex-col items-center py-28 text-center", className)}>
      <h1 className="font-display text-hf-fg-1 mx-auto mb-6 text-[clamp(3.2rem,8vw,6.5rem)] leading-[0.95] tracking-[-0.025em]">
        End-to-end <br />
        <em className="font-display italic">network pharmacology.</em>
      </h1>

      <p className="text-hf-fg-2 mx-auto mb-10 max-w-[56ch] text-[17px] leading-relaxed">
        Herbaflow runs the full network-pharmacology workflow as one continuous, reviewable
        pipeline: from the bioactive compounds in a medicinal plant, to the human proteins they act
        on, to the diseases those proteins drive. Every parameter is yours to set. Every association
        carries its source.
      </p>

      {/* Single liquid-glass CTA. Reuses Button variant="glass-action" via asChild
          so the router Link renders the glass pill as one anchor (valid HTML). */}
      <Button asChild variant="glass-action">
        <Link to="/analysis">
          Start analysis
          <span
            aria-hidden="true"
            className="bg-hf-fg-1 text-hf-bg grid size-[30px] place-items-center rounded-full"
          >
            <ArrowRight size={14} strokeWidth={1.6} />
          </span>
        </Link>
      </Button>
    </section>
  );
}
