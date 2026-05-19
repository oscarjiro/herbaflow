import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export default function LandingPage() {
  return (
    <section className="min-h-[calc(100vh-56px)] flex items-center justify-center px-6 py-16">
      <div className="flex flex-col items-center text-center gap-8 max-w-2xl">
        <div className="h-40 flex items-center justify-center">
          <ascii-dna />
        </div>

        <div className="flex flex-col items-center gap-3">
          <h1 className="font-display text-6xl text-hf-fg1 leading-tight">
            Herbaflow
          </h1>
          <p className="font-sans text-lg text-hf-fg2">
            Network pharmacology for Indonesian medicinal plants
          </p>
        </div>

        <p className="font-sans text-base text-hf-fg3 leading-relaxed">
          Herbaflow maps plant-compound-disease-target relationships sourced from the KNApSAcK
          database, enabling systematic network pharmacology analysis. Choose between guided mode
          — with manual approval at each pipeline stage — or auto mode for fully automatic
          end-to-end processing.
        </p>

        <Button asChild variant="default" size="lg" className="rounded-sm">
          <Link to="/analysis">Start Analysis</Link>
        </Button>
      </div>
    </section>
  )
}
