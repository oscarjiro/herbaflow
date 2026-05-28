import { ExternalLink as ExternalLinkIcon } from 'lucide-react'

interface ExternalLinkProps {
  href: string
  children: React.ReactNode
  className?: string
}

export function ExternalLink({ href, children, className }: ExternalLinkProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 hover:underline ${className ?? ''}`}
    >
      {children}
      <ExternalLinkIcon className="h-3 w-3 shrink-0 opacity-70" />
    </a>
  )
}
