import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockApi, renderRoute } from '@/test/utils';
import { AdminPage } from './AdminPage';

afterEach(() => vi.unstubAllGlobals());

const metrics = {
  notes_total: 10,
  notes_by_status: { APPROVED: 6, REJECTED: 1, PENDING_REVIEW: 2, FAILED_VALIDATION: 1 },
  approval_rate: 6 / 7,
  edit_rate: 0.5,
  mean_edit_ratio: 0.1234,
  validation_failure_rate: 0.05,
  llm_calls: 20,
  llm_latency_ms_p50: 820,
  llm_latency_ms_p95: 2400,
  time_to_summary_s_p50: 3.2,
  time_to_summary_s_p95: 12,
  input_tokens: 12345,
  output_tokens: 2345,
  cost_usd_total: 0.4,
  cost_usd_per_note: 0.04,
};

describe('AdminPage', () => {
  it('shows quality, latency and cost figures with readable formatting', async () => {
    mockApi({ 'GET /admin/metrics': metrics });
    renderRoute(<AdminPage />);
    expect(await screen.findByText('86%')).toBeInTheDocument(); // approval
    expect(screen.getByText('5.0%')).toBeInTheDocument(); // validation failures
    expect(screen.getByText('$0.04')).toBeInTheDocument();
    expect(screen.getByText('820 ms')).toBeInTheDocument();
    expect(screen.getByText('2.4 s')).toBeInTheDocument();
    expect(screen.getByText('12,345 / 2,345')).toBeInTheDocument();
    const statuses = screen.getByRole('region', { name: 'Notes by status' });
    expect(within(statuses).getByText('Approved').parentElement).toHaveTextContent('6 · 60%');
  });

  it('switches to the audit log and lists identifiers only', async () => {
    mockApi({
      'GET /admin/metrics': metrics,
      'GET /admin/audit': {
        total: 1,
        items: [
          {
            id: 1,
            occurred_at: '2026-10-12T10:00:00Z',
            actor_id: 'u1',
            actor_role: 'clinician',
            action: 'summary.approved',
            entity_type: 'summary',
            entity_id: '1234567890abcdef',
            request_id: 'abcdef123456',
            model: 'fake-extractor-v1',
            prompt_version: 'v1',
            schema_version: '1.0',
            details: { edit_ratio: 0.1 },
          },
        ],
      },
    });
    renderRoute(<AdminPage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('tab', { name: 'Audit log' }));
    const table = await screen.findByRole('table');
    expect(within(table).getByText('summary.approved')).toBeInTheDocument();
    expect(within(table).getByText('12345678')).toBeInTheDocument();
    expect(table).toHaveTextContent('"edit_ratio":0.1');
  });
});
