import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mockApi } from '@/test/utils';
import { AuthProvider, useAuth } from './auth';

function Probe() {
  const { user, loading, error, retry } = useAuth();
  return (
    <div>
      <p>{loading ? 'loading' : user ? `user:${user.email}` : error ? `error:${error}` : 'signed-out'}</p>
      <button onClick={retry}>retry</button>
    </div>
  );
}

const open = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );

const me = { id: 'u1', email: 'a@demo.example', role: 'clinician', display_name: 'A' };

beforeEach(() => sessionStorage.setItem('cda.token', 'stored-token'));
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe('session restore', () => {
  it('restores the user from a stored token', async () => {
    mockApi({ 'GET /me': me });
    open();
    expect(await screen.findByText('user:a@demo.example')).toBeInTheDocument();
  });

  it('keeps the session when the server fails or is unreachable, and lets the person retry', async () => {
    let calls = 0;
    mockApi({
      'GET /me': () => {
        calls += 1;
        return calls === 1 ? new Response(JSON.stringify({ detail: 'restarting' }), { status: 503 }) : me;
      },
    });
    open();
    expect(await screen.findByText(/error:/)).toBeInTheDocument();
    expect(sessionStorage.getItem('cda.token')).toBe('stored-token'); // not signed out
    await userEvent.setup().click(screen.getByText('retry'));
    expect(await screen.findByText('user:a@demo.example')).toBeInTheDocument();
  });

  it('does not sign out when the request is cancelled by a navigation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    open();
    expect(await screen.findByText(/error:Cannot reach the server/)).toBeInTheDocument();
    expect(sessionStorage.getItem('cda.token')).toBe('stored-token');
  });

  it('ends the session only when the server says the token is invalid', async () => {
    mockApi({ 'GET /me': new Response(JSON.stringify({ detail: 'invalid or expired token' }), { status: 401 }) });
    open();
    await waitFor(() => expect(screen.getByText('signed-out')).toBeInTheDocument());
    expect(sessionStorage.getItem('cda.token')).toBeNull();
  });
});
