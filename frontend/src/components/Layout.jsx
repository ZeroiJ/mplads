import { Outlet, NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Upload' },
  { to: '/results', label: 'Results' },
  { to: '/mp-rankings', label: 'MP Rankings' },
  { to: '/similarity', label: 'Similarity' },
]

export default function Layout() {
  return (
    <>
      <nav className="nav">
        <div className="nav-inner">
          <NavLink to="/" className="nav-brand">
            <span className="mono-sm">MPLADS</span>
            <span style={{ color: 'var(--gray-400)' }}>/</span>
            <span>Fraud Detection</span>
          </NavLink>
          <div className="nav-links">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === '/'}
                className={({ isActive }) =>
                  `nav-link ${isActive ? 'nav-link-active' : ''}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>
      <main>
        <Outlet />
      </main>
    </>
  )
}
