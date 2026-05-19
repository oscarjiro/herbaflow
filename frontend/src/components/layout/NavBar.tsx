import { Link } from 'react-router-dom'

export default function NavBar() {
  return (
    <nav className="h-14 bg-hf-surface border-b border-hf-border flex items-center justify-between px-6">
      <Link to="/" className="font-display text-xl text-hf-fg1 hover:text-hf-fg2 transition-colors">
        Herbaflow
      </Link>
      <Link to="/about" className="font-sans text-sm text-hf-fg2 hover:text-hf-fg1 transition-colors">
        About
      </Link>
    </nav>
  )
}
