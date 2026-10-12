import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockApi, noteFixture, renderRoute } from '@/test/utils';
import { NotesPage } from './NotesPage';

afterEach(() => vi.unstubAllGlobals());
const open = (route = '/') => renderRoute(<NotesPage />, { path: '/', route });
const item = (over: Record<string, unknown>) => {
  const note: Record<string, unknown> = { ...noteFixture(over) };
  delete note.body;
  delete note.summary;
  return note;
};

describe('NotesPage', () => {
  it('lists notes with a text status and links to each review', async () => {
    mockApi({
      'GET /notes': {
        total: 2,
        items: [
          item({ id: 'a', title: 'Cough', status: 'PENDING_REVIEW' }),
          item({ id: 'b', title: null, status: 'APPROVED' }),
        ],
      },
    });
    open();
    const link = await screen.findByRole('link', { name: /Cough/ });
    expect(link).toHaveAttribute('href', '/notes/a');
    expect(within(link).getByText('Needs review')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Untitled note/ })).toHaveTextContent('Approved');
  });

  it('filters by status through the query string and exposes pressed state', async () => {
    const { calls } = mockApi({ 'GET /notes': { total: 0, items: [] } });
    open();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Needs review' }));
    expect(await screen.findByRole('button', { name: 'Needs review', pressed: true })).toBeInTheDocument();
    expect(calls.length).toBeGreaterThan(1);
    expect(screen.getByText('No notes with this status')).toBeInTheDocument();
  });

  it('invites the first submission when empty', async () => {
    mockApi({ 'GET /notes': { total: 0, items: [] } });
    open();
    expect(await screen.findByText('No notes yet')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /New note/ }).length).toBeGreaterThan(0);
  });

  it('offers a retry when loading fails', async () => {
    mockApi({ 'GET /notes': new Response(JSON.stringify({ detail: 'boom' }), { status: 500 }) });
    open();
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });
});
