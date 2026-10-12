import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockApi, noteFixture, renderRoute, summaryFixture } from '@/test/utils';
import { ReviewPage } from './ReviewPage';

const open = () => renderRoute(<ReviewPage />, { path: '/notes/:id', route: '/notes/n1' });

afterEach(() => vi.unstubAllGlobals());

describe('ReviewPage', () => {
  it('shows a live progress state while the note is processing', async () => {
    mockApi({ 'GET /notes/n1': noteFixture({ status: 'PROCESSING', summary: null }) });
    open();
    expect(await screen.findByText('Preparing your summary…')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Processing');
    expect(screen.getByText(/Anna Beispiel presents/)).toBeInTheDocument(); // note stays visible
  });

  it('renders fields with labelled confidence and "not documented" states', async () => {
    mockApi({ 'GET /notes/n1': noteFixture() });
    open();
    const chief = await screen.findByRole('region', { name: 'Chief complaint' });
    expect(within(chief).getByRole('textbox')).toHaveValue('Anna Beispiel presents with cough for three days.');
    expect(within(chief).getByText('High confidence · 90%')).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Allergies mentioned' })).getByText('Low confidence · 40%'),
    ).toBeInTheDocument();
    const hpi = screen.getByRole('region', { name: 'History of present illness' });
    expect(within(hpi).getByText('Not documented')).toBeInTheDocument();
    expect(within(hpi).getByRole('textbox')).toHaveAttribute('placeholder', 'Not documented in the note');
  });

  it('highlights the supporting text for the chosen field', async () => {
    mockApi({ 'GET /notes/n1': noteFixture() });
    open();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Show source for Plan' }));
    const note = screen.getByRole('region', { name: 'Note text' });
    const marks = within(note).getAllByText('Plan: rest and fluids.');
    expect(marks[0]?.tagName).toBe('MARK');
    expect(screen.getByText('Showing evidence for Plan')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show source for Medications mentioned' }));
    expect(within(note).getByText('Takes ramipril 5 mg once daily.').tagName).toBe('MARK');
    expect(within(note).queryByText('Plan: rest and fluids.')).not.toBeInTheDocument();
  });

  it('saves a draft with the edit and keeps source spans', async () => {
    const { calls } = mockApi({
      'GET /notes/n1': noteFixture(),
      'PUT /notes/n1/summary': { id: 's1' },
    });
    open();
    const user = userEvent.setup();
    const plan = within(await screen.findByRole('region', { name: 'Plan' })).getByRole('textbox');
    await user.clear(plan);
    await user.type(plan, 'Rest, fluids and paracetamol.');
    expect(screen.getByText('Unsaved changes in 1 field(s)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Save draft/ }));
    await waitFor(() => expect(calls.some((c) => c.key === 'PUT /notes/n1/summary')).toBe(true));
    const sent = calls.find((c) => c.key === 'PUT /notes/n1/summary')?.body as ReturnType<typeof summaryFixture>;
    expect(sent.plan.value).toBe('Rest, fluids and paracetamol.');
    expect(sent.plan.source_spans).toHaveLength(1);
    expect(sent.chief_complaint).toEqual(summaryFixture().chief_complaint);
  });

  it('approves after confirming, saving pending edits first', async () => {
    const { calls } = mockApi({
      'GET /notes/n1': noteFixture(),
      'PUT /notes/n1/summary': { id: 's1' },
      'POST /notes/n1/approve': { id: 's1' },
    });
    open();
    const user = userEvent.setup();
    const plan = within(await screen.findByRole('region', { name: 'Plan' })).getByRole('textbox');
    await user.type(plan, ' Review in a week.');
    await user.click(screen.getByRole('button', { name: /^Approve$/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Approve this summary?' });
    expect(dialog).toHaveTextContent('1 field(s) changed');
    await user.click(within(dialog).getByRole('button', { name: 'Approve summary' }));
    await waitFor(() => expect(calls.map((c) => c.key)).toContain('POST /notes/n1/approve'));
    const order = calls.map((c) => c.key).filter((k) => k !== 'GET /notes/n1');
    expect(order).toEqual(['PUT /notes/n1/summary', 'POST /notes/n1/approve']);
  });

  it('blocks approval and explains when a medication row has no name', async () => {
    const { calls } = mockApi({ 'GET /notes/n1': noteFixture() });
    open();
    const user = userEvent.setup();
    await screen.findByRole('region', { name: 'Medications mentioned' });
    await user.click(screen.getByRole('button', { name: 'Add medication' }));
    await user.click(screen.getByRole('button', { name: /^Approve$/ }));
    expect(await screen.findByText('Enter the medication name')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Fix the highlighted fields before approving.');
    expect(calls.some((c) => c.key.includes('approve'))).toBe(false);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('requires a reason to reject', async () => {
    const { calls } = mockApi({ 'GET /notes/n1': noteFixture(), 'POST /notes/n1/reject': { id: 's1' } });
    open();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /^Reject$/ }));
    const dialog = await screen.findByRole('dialog', { name: 'Reject this summary' });
    await user.click(within(dialog).getByRole('button', { name: 'Reject summary' }));
    expect(within(dialog).getByText('Enter a reason (at least 3 characters)')).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText('Reason'), 'Wrong note');
    await user.click(within(dialog).getByRole('button', { name: 'Reject summary' }));
    await waitFor(() =>
      expect(calls.find((c) => c.key === 'POST /notes/n1/reject')?.body).toEqual({ reason: 'Wrong note' }),
    );
  });

  it('shows a read-only final summary with an edit digest once approved', async () => {
    const approved = noteFixture({ status: 'APPROVED' });
    approved.summary = {
      ...approved.summary,
      approved_content: summaryFixture(),
      reviewed_at: '2026-10-12T11:00:00Z',
      diff: { changed_fields: { plan: {} }, edit_ratio: 0.12 },
    };
    mockApi({ 'GET /notes/n1': approved });
    open();
    expect(await screen.findByText('Approved — this summary is final')).toBeInTheDocument();
    expect(screen.getByText(/1 field\(s\) edited \(12% of content changed\)/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Approve$/ })).not.toBeInTheDocument();
    expect(screen.queryAllByRole('textbox')).toHaveLength(0);
  });

  it('offers a retry with a plain-language reason when processing failed', async () => {
    const { calls } = mockApi({
      'GET /notes/n1': noteFixture({ status: 'FAILED_VALIDATION', failure_reason: 'llm_unavailable', summary: null }),
      'POST /notes/n1/regenerate': { id: 'n1' },
    });
    open();
    const user = userEvent.setup();
    expect(await screen.findByText(/language model service was not reachable/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Try again/ }));
    await waitFor(() => expect(calls.some((c) => c.key === 'POST /notes/n1/regenerate')).toBe(true));
  });

  it('explains a missing note without leaking whether it exists', async () => {
    mockApi({ 'GET /notes/n1': new Response(JSON.stringify({ detail: 'note not found' }), { status: 404 }) });
    open();
    expect(await screen.findByText(/does not exist or you do not have access/)).toBeInTheDocument();
  });
});

describe('ReviewPage explicit absence', () => {
  it('labels a field the note states as none differently from one it never mentions', async () => {
    const note = noteFixture();
    const content = summaryFixture();
    content.medications = {
      value: [],
      confidence: 0.9,
      source_spans: [{ start: 0, end: 20, text: 'Anna Beispiel presen' }],
    };
    note.summary = { ...note.summary, content };
    mockApi({ 'GET /notes/n1': note });
    open();
    const meds = await screen.findByRole('region', { name: 'Medications mentioned' });
    expect(within(meds).getByText('Stated as none')).toBeInTheDocument();
    const hpi = screen.getByRole('region', { name: 'History of present illness' });
    expect(within(hpi).getByText('Not documented')).toBeInTheDocument();
  });
});
