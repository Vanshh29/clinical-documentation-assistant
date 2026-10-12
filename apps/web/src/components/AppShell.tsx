import { FileText, LogOut, PlusCircle, ShieldCheck, Gauge, Lock } from 'lucide-react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';

const link = ({ isActive }: { isActive: boolean }) =>
  `inline-flex items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors duration-150 ${
    isActive ? 'bg-primary/10 text-primary' : 'text-muted hover:bg-surface-2 hover:text-fg'
  }`;

export function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin';

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-on-primary"
      >
        Skip to main content
      </a>
      <div role="note" className="bg-warning-soft px-4 py-1.5 text-center text-xs font-semibold text-warning">
        Demo only. Not a medical device. Not for real patient data.
      </div>
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2 sm:px-6">
          <NavLink
            to={isAdmin ? '/admin' : '/'}
            className="flex items-center gap-2 py-1.5 font-display text-base font-bold"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-on-primary">
              <FileText className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="hidden sm:inline">Clinical Documentation Assistant</span>
            <span className="sm:hidden">CDA</span>
          </NavLink>
          <nav aria-label="Main" className="flex flex-1 flex-wrap gap-1">
            {!isAdmin && (
              <>
                <NavLink to="/" end className={link} style={{ minHeight: 44, minWidth: 44 }}>
                  <FileText className="h-4 w-4" aria-hidden="true" />
                  <span className="sr-only sm:not-sr-only">Notes</span>
                </NavLink>
                <NavLink to="/notes/new" className={link} style={{ minHeight: 44, minWidth: 44 }}>
                  <PlusCircle className="h-4 w-4" aria-hidden="true" />
                  <span className="sr-only sm:not-sr-only">New note</span>
                </NavLink>
                <NavLink to="/privacy" className={link} style={{ minHeight: 44, minWidth: 44 }}>
                  <Lock className="h-4 w-4" aria-hidden="true" />
                  <span className="sr-only sm:not-sr-only">Privacy</span>
                </NavLink>
              </>
            )}
            {isAdmin && (
              <NavLink to="/admin" className={link} style={{ minHeight: 44, minWidth: 44 }}>
                <Gauge className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only sm:not-sr-only">Metrics &amp; audit</span>
              </NavLink>
            )}
          </nav>
          <div className="flex items-center gap-3">
            <div className="hidden text-right leading-tight sm:block">
              <div className="text-sm font-semibold">{user?.display_name}</div>
              <div className="flex items-center justify-end gap-1 text-xs capitalize text-muted">
                <ShieldCheck className="h-3 w-3" aria-hidden="true" /> {user?.role}
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                logout();
                navigate('/login');
              }}
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only sm:not-sr-only">Sign out</span>
            </button>
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  );
}
