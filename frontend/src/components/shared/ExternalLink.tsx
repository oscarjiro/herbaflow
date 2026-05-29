import { ExternalLink as ExternalLinkIcon } from 'lucide-react'

interface ExternalLinkProps {
  href: string
  children: React.ReactNode
  className?: string
}

export function ExternalLink({ href, children, className }: ExternalLinkProps) {
  if (!href.startsWith('https://') && !href.startsWith('http://')) {
    if (process.env.NODE_ENV !== 'production') {
      console.warn(`ExternalLink: unsafe href blocked: ${href}`)
    }
    return <span className={className}>{children}</span>
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1 text-hf-info hover:text-hf-fg1 hover:underline ${className ?? ''}`}
    >
      {children}
      <ExternalLinkIcon aria-hidden={true} className="h-3 w-3 shrink-0 opacity-70" />
    </a>
  )
}
