import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '@/lib/auth';
import { mockApi } from '@/test/utils';
import { LoginPage } from './LoginPage';

const open = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/login']}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<div>notes home</div>} />
            <Route path="/admin" element={<div>admin home</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe('LoginPage', () => {
  it('validates both fields with messages tied to the inputs', async () => {
    mockApi({});
    open();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Enter your email address')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Email')).toHaveAccessibleDescription('Enter your email address');
    expect(screen.getByText('Enter your password')).toBeInTheDocument();
  });

  it('shows the server message for bad credentials and stays on the page', async () => {
    mockApi({ 'POST /auth/token': new Response(JSON.stringify({ detail: 'invalid credentials' }), { status: 401 }) });
    open();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Email'), 'someone@demo.example');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('invalid credentials');
    expect(screen.queryByText('notes home')).not.toBeInTheDocument();
  });

  it('signs a clinician in and routes by role', async () => {
    mockApi({
      'POST /auth/token': { access_token: 't', token_type: 'bearer', expires_in: 1800 },
      'GET /me': { id: 'u1', email: 'clinician1@demo.example', role: 'clinician', display_name: 'Dr. Demo' },
    });
    open();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Fill clinician login' }));
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(screen.getByText('notes home')).toBeInTheDocument());
    expect(sessionStorage.getItem('cda.token')).toBe('t');
  });
});
