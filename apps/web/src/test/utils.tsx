import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import { ToastProvider } from '@/components/Toast';
import type { ClinicalSummary } from '@/lib/summary';

export const NOTE_BODY =
  'Anna Beispiel presents with cough for three days. Takes ramipril 5 mg once daily. No known allergies. Plan: rest and fluids.';

const span = (text: string) => {
  const start = NOTE_BODY.indexOf(text);
  return { start, end: start + text.length, text };
};
const empty = { value: null, confidence: 0, source_spans: [] };

export function summaryFixture(): ClinicalSummary {
  return {
    schema_version: '1.0',
    chief_complaint: {
      value: 'Anna Beispiel presents with cough for three days.',
      confidence: 0.9,
      source_spans: [span('Anna Beispiel presents with cough for three days.')],
    },
    history_of_present_illness: empty,
    medications: {
      value: [{ name: 'ramipril', dose: '5 mg', frequency: 'once daily' }],
      confidence: 0.7,
      source_spans: [span('Takes ramipril 5 mg once daily.')],
    },
    allergies: { value: ['no known allergies'], confidence: 0.4, source_spans: [span('No known allergies.')] },
    assessment: empty,
    plan: { value: 'Plan: rest and fluids.', confidence: 0.85, source_spans: [span('Plan: rest and fluids.')] },
    follow_up_items: empty,
  };
}

export type NoteFixture = { summary: Record<string, unknown> | null } & Record<string, unknown>;

export function noteFixture(overrides: Record<string, unknown> = {}): NoteFixture {
  return {
    id: 'n1',
    title: 'Test note',
    language: 'en',
    source: 'paste',
    status: 'PENDING_REVIEW',
    failure_reason: null,
    generation: 1,
    created_at: '2026-10-12T10:00:00Z',
    updated_at: '2026-10-12T10:00:00Z',
    body: NOTE_BODY,
    summary: {
      id: 's1',
      generation: 1,
      schema_version: '1.0',
      model: 'fake-extractor-v1',
      prompt_version: 'v1',
      content: summaryFixture(),
      edited_content: null,
      approved_content: null,
      diff: null,
      rejection_reason: null,
      reviewed_at: null,
      created_at: '2026-10-12T10:00:05Z',
    },
    ...overrides,
  } as NoteFixture;
}

type Handler = (url: string, init: RequestInit) => unknown;

/** Replace fetch with a routing stub. Keys look like "GET /notes/n1". */
export function mockApi(routes: Record<string, Handler | unknown>) {
  const calls: { key: string; body: unknown }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input).replace(/^\/api/, '');
    const key = `${init.method ?? 'GET'} ${url.split('?')[0]}`;
    calls.push({ key, body: init.body ? JSON.parse(String(init.body)) : undefined });
    const route = routes[key];
    if (route === undefined) return new Response(JSON.stringify({ detail: `no mock for ${key}` }), { status: 500 });
    const out = typeof route === 'function' ? (route as Handler)(url, init) : route;
    if (out instanceof Response) return out;
    return new Response(JSON.stringify(out), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fn);
  return { calls, fn };
}

export function renderRoute(ui: ReactElement, { path = '/', route = '/' } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={ui} />
            <Route path="*" element={<div>elsewhere</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}
