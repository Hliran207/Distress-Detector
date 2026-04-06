import { Link, NavLink, Outlet } from 'react-router-dom'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  [
    'px-3 py-2 rounded-md text-sm font-medium',
    isActive ? 'bg-slate-900 text-white' : 'text-slate-700 hover_bg-slate-100',
  ].join(' ')

export function Layout() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b border-slate-200">
        <div className="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
          <Link to="/" className="font-semibold">
            Distress-Detector Dashboard
          </Link>
          <nav className="flex gap-2">
            <NavLink to="/" className={navLinkClass} end>
              Summary
            </NavLink>
            <NavLink to="/posts" className={navLinkClass}>
              Posts
            </NavLink>
            <NavLink to="/search" className={navLinkClass}>
              Search
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 mt-10">
        <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">
          Backend: FastAPI · Data: MongoDB Atlas
        </div>
      </footer>
    </div>
  )
}
