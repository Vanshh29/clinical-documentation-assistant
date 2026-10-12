import { zodResolver } from '@hookform/resolvers/zod';
import { FileText, LogIn } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { useAuth } from '@/lib/auth';

const schema = z.object({
  email: z.string().trim().min(1, 'Enter your email address').email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
});
type Values = z.infer<typeof schema>;

const DEMO = [
  { label: 'Clinician', email: 'clinician1@demo.example' },
  { label: 'Admin', email: 'admin@demo.example' },
];

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  if (user) return <Navigate to={user.role === 'admin' ? '/admin' : '/'} replace />;

  const from = (location.state as { from?: string } | null)?.from;

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const me = await login(values.email, values.password);
      navigate(from ?? (me.role === 'admin' ? '/admin' : '/'), {
        replace: true,
      });
    } catch (e) {
      setServerError(e instanceof Error ? e.message : 'Sign in failed.');
    }
  });

  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <div
          role="note"
          className="mb-4 rounded-lg bg-warning-soft px-4 py-2 text-center text-sm font-semibold text-warning"
        >
          Demo only. Not a medical device. Not for real patient data.
        </div>
        <div className="card p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary text-on-primary">
              <FileText className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <h1 className="text-xl font-bold leading-tight">Clinical Documentation Assistant</h1>
              <p className="text-sm text-muted">Sign in to review structured note summaries</p>
            </div>
          </div>

          {serverError && (
            <div
              role="alert"
              className="mb-4 rounded-lg border border-danger/40 bg-danger-soft p-3 text-sm font-medium text-danger"
            >
              {serverError}
            </div>
          )}

          <form onSubmit={onSubmit} noValidate className="space-y-4">
            <div>
              <label htmlFor="email" className="label">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                className="input"
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? 'email-error' : undefined}
                {...register('email')}
              />
              {errors.email && (
                <p id="email-error" className="error-text">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="password" className="label">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="input"
                aria-invalid={!!errors.password}
                aria-describedby={errors.password ? 'password-error' : undefined}
                {...register('password')}
              />
              {errors.password && (
                <p id="password-error" className="error-text">
                  {errors.password.message}
                </p>
              )}
            </div>
            <button type="submit" className="btn btn-primary w-full" disabled={isSubmitting}>
              <LogIn className="h-4 w-4" aria-hidden="true" />
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          {import.meta.env.VITE_DEMO_HINTS !== 'false' && (
            <div className="mt-6 border-t border-line pt-4">
              <p className="mb-2 text-sm text-muted">Local demo accounts (password: demo-password-123)</p>
              <div className="flex flex-wrap gap-2">
                {DEMO.map((d) => (
                  <button
                    key={d.email}
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setValue('email', d.email);
                      setValue('password', 'demo-password-123');
                    }}
                  >
                    Fill {d.label.toLowerCase()} login
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
