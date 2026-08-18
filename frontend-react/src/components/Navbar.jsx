import { Link, useLocation } from 'react-router-dom'
import { Radio, Terminal, Wrench } from 'lucide-react'

const LINKS = [
  { to: '/console', label: 'Console', icon: Terminal },
  { to: '/heal', label: 'Heal Lab', icon: Wrench },
]

export default function Navbar({ variant = 'default' }) {
  const { pathname } = useLocation()
  const isHome = pathname === '/'

  return (
    <nav className={`site-nav ${variant}`}>
      <div className="site-nav-inner">
        <Link to="/" className="site-logo mono">
          <Radio size={18} className="logo-icon" />
          SIGNAL
          <span className="logo-pulse" />
        </Link>

        <div className="site-nav-links">
          {LINKS.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={`nav-link mono ${pathname === to ? 'active' : ''}`}
            >
              <Icon size={14} />
              <span className="nav-link-text">{label}</span>
            </Link>
          ))}
        </div>

        {!isHome && (
          <Link to="/console" className="nav-cta mono">
            Launch console →
          </Link>
        )}
        {isHome && (
          <Link to="/console" className="nav-cta mono nav-cta-primary">
            Launch console →
          </Link>
        )}
      </div>
    </nav>
  )
}
