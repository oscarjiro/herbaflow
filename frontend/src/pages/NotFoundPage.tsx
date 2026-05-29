import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <section className="min-h-[calc(100vh-56px)] flex items-center justify-center px-6 py-16">
      <div className="flex flex-col items-center text-center gap-6 max-w-md">
        <p className="font-display text-6xl text-hf-fg3 leading-none">404</p>
        <div className="flex flex-col items-center gap-2">
          <h1 className="font-display text-3xl text-hf-fg1">Page not found</h1>
          <p className="font-sans text-base text-hf-fg2 leading-relaxed">
            The page you are looking for does not exist or may have moved.
          </p>
        </div>
        <Button asChild variant="default" size="lg" className="rounded-sm">
          <Link to="/">Back to Home</Link>
        </Button>
      </div>
    </section>
  )
}
