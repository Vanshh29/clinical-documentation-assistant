import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { ErrorState, PageHeader, PageLoading } from '@/components/feedback';
import { STATUS_LABEL } from '@/components/StatusBadge';
import { formatDateTime, formatMs, formatNumber, formatPercent, formatSeconds, formatUsd } from '@/lib/format';
import { useAudit, useMetrics } from '@/lib/queries';
import type { Metrics, NoteStatus } from '@/lib/types';

const STATUS_ORDER: NoteStatus[] = [
  'SUBMITTED',
  'PROCESSING',
  'PENDING_REVIEW',
  'APPROVED',
  'REJECTED',
  'FAILED_VALIDATION',
];

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card p-4">
      <dt className="text-sm font-semibold text-muted">{label}</dt>
      <dd className="mt-1 font-display text-3xl font-bold tabular-nums">{value}</dd>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

function StatusBars({ counts, total }: { counts: Record<string, number>; total: number }) {
  const max = Math.max(1, ...STATUS_ORDER.map((s) => counts[s] ?? 0));
  return (
    <section aria-labelledby="status-title" className="card p-5">
      <h2 id="status-title" className="mb-4 text-base font-bold">
        Notes by status
      </h2>
      <ul className="space-y-3">
        {STATUS_ORDER.map((s) => {
          const n = counts[s] ?? 0;
          return (
            <li
              key={s}
              className="grid grid-cols-[8.5rem_1fr_6.5rem] items-center gap-3 text-sm sm:grid-cols-[10rem_1fr_7rem]"
            >
              <span className="font-medium">{STATUS_LABEL(s)}</span>
              <span className="h-2.5 rounded-r bg-surface-2" aria-hidden="true">
                <span
                  className="block h-full rounded-r bg-primary transition-[width] duration-300 motion-reduce:transition-none"
                  style={{ width: `${(n / max) * 100}%` }}
                  title={`${STATUS_LABEL(s)}: ${n}`}
                />
              </span>
              <span className="text-right tabular-nums text-muted">
                <span className="font-semibold text-fg">{formatNumber(n)}</span> ·{' '}
                {total ? Math.round((n / total) * 100) : 0}%
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function MetricsView({ m }: { m: Metrics }) {
  return (
    <div className="space-y-6">
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Approval rate"
          value={formatPercent(m.approval_rate)}
          hint="Approved of reviewed (approved + rejected)"
        />
        <Kpi
          label="Edit rate"
          value={formatPercent(m.edit_rate)}
          hint={`Mean change when edited: ${formatPercent(m.mean_edit_ratio, 1)}`}
        />
        <Kpi
          label="Validation failure rate"
          value={formatPercent(m.validation_failure_rate, 1)}
          hint={`${formatNumber(m.llm_calls)} model calls`}
        />
        <Kpi
          label="Cost per note"
          value={formatUsd(m.cost_usd_per_note)}
          hint={`Total ${formatUsd(m.cost_usd_total)} (estimated)`}
        />
      </dl>
      <StatusBars counts={m.notes_by_status} total={m.notes_total} />
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[28rem] text-left text-sm">
          <caption className="px-5 pb-1 pt-4 text-left text-base font-bold">Processing and usage</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="px-5 py-2 font-semibold">
                Measure
              </th>
              <th scope="col" className="px-5 py-2 text-right font-semibold">
                Median (p50)
              </th>
              <th scope="col" className="px-5 py-2 text-right font-semibold">
                p95
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line tabular-nums">
            <tr>
              <th scope="row" className="px-5 py-3 font-medium">
                Model latency
              </th>
              <td className="px-5 py-3 text-right">{formatMs(m.llm_latency_ms_p50)}</td>
              <td className="px-5 py-3 text-right">{formatMs(m.llm_latency_ms_p95)}</td>
            </tr>
            <tr>
              <th scope="row" className="px-5 py-3 font-medium">
                Submit to summary ready
              </th>
              <td className="px-5 py-3 text-right">{formatSeconds(m.time_to_summary_s_p50)}</td>
              <td className="px-5 py-3 text-right">{formatSeconds(m.time_to_summary_s_p95)}</td>
            </tr>
            <tr>
              <th scope="row" className="px-5 py-3 font-medium">
                Tokens (input / output)
              </th>
              <td className="px-5 py-3 text-right" colSpan={2}>
                {formatNumber(m.input_tokens)} / {formatNumber(m.output_tokens)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

const ACTIONS = [
  '',
  'note.submitted',
  'processing.started',
  'summary.generated',
  'processing.failed',
  'summary.edited',
  'summary.approved',
  'summary.rejected',
  'summary.regeneration_requested',
  'data.erased',
  'auth.login',
];

function AuditView() {
  const [action, setAction] = useState('');
  const [page, setPage] = useState(0);
  const { data, isPending, isError, error, refetch } = useAudit(action, page);
  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="audit-action" className="label">
          Filter by action
        </label>
        <select
          id="audit-action"
          className="input max-w-xs"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(0);
          }}
        >
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a || 'All actions'}
            </option>
          ))}
        </select>
      </div>
      {isPending ? (
        <PageLoading label="Loading audit log" />
      ) : isError ? (
        <ErrorState message={error.message} onRetry={() => void refetch()} />
      ) : (
        <>
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <caption className="sr-only">
                Audit log, newest first. Contains identifiers only, never note text.
              </caption>
              <thead className="border-b border-line text-muted">
                <tr>
                  {['When', 'Action', 'Actor', 'Entity', 'Model / prompt', 'Request'].map((h) => (
                    <th key={h} scope="col" className="px-4 py-3 font-semibold">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((e) => (
                  <tr key={e.id} className="align-top">
                    <td className="whitespace-nowrap px-4 py-3">{formatDateTime(e.occurred_at)}</td>
                    <td className="px-4 py-3 font-mono text-xs">{e.action}</td>
                    <td className="px-4 py-3 capitalize">{e.actor_role ?? 'system'}</td>
                    <td className="px-4 py-3">
                      {e.entity_type}
                      {e.entity_id && (
                        <span className="block font-mono text-xs text-muted">{e.entity_id.slice(0, 8)}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {e.model ? `${e.model} · ${e.prompt_version ?? ''}` : '—'}
                      {Object.keys(e.details).length > 0 && (
                        <span className="block font-mono text-muted">{JSON.stringify(e.details)}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted">{e.request_id?.slice(0, 8) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav aria-label="Audit pagination" className="flex items-center justify-between text-sm text-muted">
            <span>{data.total} entries</span>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" /> Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={(page + 1) * 25 >= data.total}
                onClick={() => setPage(page + 1)}
              >
                Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </nav>
        </>
      )}
    </div>
  );
}

export function AdminPage() {
  const [tab, setTab] = useState<'metrics' | 'audit'>('metrics');
  const metrics = useMetrics();
  const tabs: { id: 'metrics' | 'audit'; label: string }[] = [
    { id: 'metrics', label: 'Metrics' },
    { id: 'audit', label: 'Audit log' },
  ];
  const metricsBody = metrics.isPending ? (
    <PageLoading label="Loading metrics" />
  ) : metrics.isError ? (
    <ErrorState message={metrics.error.message} onRetry={() => void metrics.refetch()} />
  ) : (
    <MetricsView m={metrics.data} />
  );
  const body: ReactNode = tab === 'audit' ? <AuditView /> : metricsBody;

  return (
    <>
      <PageHeader
        title="Metrics & audit"
        subtitle="Aggregate quality and cost, and the append-only record of who did what. Note text is never shown here."
      />
      <div role="tablist" aria-label="Admin sections" className="mb-5 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="admin-panel"
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') setTab(tab === 'metrics' ? 'audit' : 'metrics');
            }}
            className={`-mb-px min-h-11 border-b-2 px-4 text-sm font-semibold transition-colors duration-150 ${
              tab === t.id ? 'border-primary text-primary' : 'border-transparent text-muted hover:text-fg'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="admin-panel" aria-labelledby={`tab-${tab}`}>
        {body}
      </div>
    </>
  );
}
