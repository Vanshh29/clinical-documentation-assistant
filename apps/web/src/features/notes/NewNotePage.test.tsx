import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockApi, renderRoute } from '@/test/utils';
import { NewNotePage } from './NewNotePage';

const open = () => renderRoute(<NewNotePage />, { path: '/notes/new', route: '/notes/new' });
afterEach(() => vi.unstubAllGlobals());

describe('NewNotePage', () => {
  it('shows a focused error summary linking to the invalid field', async () => {
    mockApi({});
    open();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Submit for summary/ }));
    const summary = await screen.findByRole('alert');
    expect(summary).toHaveTextContent('There is a problem');
    expect(screen.getByRole('link', { name: 'Enter at least 20 characters of note text' })).toHaveAttribute(
      'href',
      '#body',
    );
    await waitFor(() => expect(summary).toHaveFocus());
  });

  it('fills a fictional example and submits it, then opens the note', async () => {
    const { calls } = mockApi({ 'POST /notes': { id: 'new1' } });
    open();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /German example/ }));
    expect((screen.getByLabelText('Note text') as HTMLTextAreaElement).value).toContain('Anna Beispiel');
    await user.click(screen.getByRole('button', { name: /Submit for summary/ }));
    await waitFor(() => expect(screen.getByText('elsewhere')).toBeInTheDocument());
    const sent = calls.find((c) => c.key === 'POST /notes')?.body as Record<string, string>;
    expect(sent).toMatchObject({ language: 'de', source: 'paste' });
  });

  it('marks text from an uploaded file as an upload', async () => {
    const { calls } = mockApi({ 'POST /notes': { id: 'new2' } });
    open();
    const user = userEvent.setup();
    const file = new File(['Synthetic note: patient reports a mild headache since yesterday.'], 'visit.txt', {
      type: 'text/plain',
    });
    await user.upload(screen.getByLabelText('Upload a text file'), file);
    await waitFor(() =>
      expect((screen.getByLabelText('Note text') as HTMLTextAreaElement).value).toContain('mild headache'),
    );
    expect(screen.getByLabelText(/Title/)).toHaveValue('visit');
    await user.click(screen.getByRole('button', { name: /Submit for summary/ }));
    await waitFor(() => expect(calls.find((c) => c.key === 'POST /notes')?.body).toMatchObject({ source: 'upload' }));
  });

  it('rejects files that are not plain text', async () => {
    mockApi({});
    open();
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(
      screen.getByLabelText('Upload a text file'),
      new File(['%PDF'], 'scan.pdf', { type: 'application/pdf' }),
    );
    expect(await screen.findByText('Only plain text files (.txt) are supported.')).toBeInTheDocument();
  });

  it('reports a server failure in the error summary', async () => {
    mockApi({
      'POST /notes': new Response(JSON.stringify({ detail: 'note exceeds 50000 characters' }), { status: 422 }),
    });
    open();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /English example/ }));
    await user.click(screen.getByRole('button', { name: /Submit for summary/ }));
    expect(await screen.findByRole('link', { name: 'note exceeds 50000 characters' })).toBeInTheDocument();
  });
});
