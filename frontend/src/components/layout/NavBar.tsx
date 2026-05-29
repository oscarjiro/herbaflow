import { NavLink } from 'react-router-dom'

export default function NavBar() {
  return (
    <nav
      aria-label="Primary"
      className="h-14 bg-hf-surface border-b border-hf-border flex items-center justify-between px-6"
    >
      <NavLink to="/" className="font-display text-xl text-hf-fg1 hover:text-hf-fg2 transition-colors">
        Herbaflow
      </NavLink>
      <NavLink
        to="/about"
        className={({ isActive }) =>
          `font-sans text-sm transition-colors ${
            isActive ? 'text-hf-fg1' : 'text-hf-fg2 hover:text-hf-fg1'
          }`
        }
      >
        About
      </NavLink>
    </nav>
  )
}
