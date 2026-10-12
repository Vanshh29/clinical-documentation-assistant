import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { ErrorState, PageLoading } from '@/components/feedback';
import { AdminPage } from '@/features/admin/AdminPage';
import { LoginPage } from '@/features/auth/LoginPage';
import { NewNotePage } from '@/features/notes/NewNotePage';
import { NotesPage } from '@/features/notes/NotesPage';
import { PrivacyPage } from '@/features/privacy/PrivacyPage';
import { ReviewPage } from '@/features/review/ReviewPage';
import { useAuth } from '@/lib/auth';
import type { Role } from '@/lib/types';

function RequireRole({ role }: { role: Role }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <PageLoading label="Signing in" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (user.role !== role) return <Navigate to={user.role === 'admin' ? '/admin' : '/'} replace />;
  return <Outlet />;
}

function RequireUser() {
  const { user, loading, error, retry } = useAuth();
  const location = useLocation();
  if (loading) return <PageLoading label="Signing in" />;
  if (!user && error)
    return (
      <div className="mx-auto max-w-lg px-4 py-16">
        <ErrorState message={`We could not restore your session. ${error}`} onRetry={retry} />
      </div>
    );
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <AppShell />;
}

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireUser />,
    children: [
      {
        element: <RequireRole role="clinician" />,
        children: [
          { path: '/', element: <NotesPage /> },
          { path: '/notes/new', element: <NewNotePage /> },
          { path: '/notes/:id', element: <ReviewPage /> },
          { path: '/privacy', element: <PrivacyPage /> },
        ],
      },
      {
        element: <RequireRole role="admin" />,
        children: [{ path: '/admin', element: <AdminPage /> }],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);

export function App() {
  // Route changes commit immediately. The default transition wrapping left the old page on screen
  // after the URL changed (notably leaving a note that had just been approved).
  return <RouterProvider router={router} useTransitions={false} />;
}
