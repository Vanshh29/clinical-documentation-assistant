import { ChevronLeft, ChevronRight, PlusCircle } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { EmptyState, ErrorState, PageHeader, PageLoading } from '@/components/feedback';
import { StatusBadge } from '@/components/StatusBadge';
import { formatDateTime } from '@/lib/format';
import { PAGE_SIZE, useNotes } from '@/lib/queries';
import type { NoteStatus } from '@/lib/types';

const FILTERS: { label: string; value: NoteStatus | null }[] = [
  { label: 'All', value: null },
  { label: 'Needs review', value: 'PENDING_REVIEW' },
  { label: 'Processing', value: 'PROCESSING' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Rejected', value: 'REJECTED' },
  { label: 'Failed', value: 'FAILED_VALIDATION' },
];

const LANG: Record<string, string> = {
  de: 'German',
  en: 'English',
  auto: 'Auto-detect',
};

export function NotesPage() {
  const [params, setParams] = useSearchParams();
  const status = (params.get('status') as NoteStatus | null) ?? null;
  const page = Math.max(0, Number(params.get('page') ?? 0) || 0);
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useNotes(status, page);

  const setFilter = (value: NoteStatus | null) => setParams(value ? { status: value } : {});
  const setPage = (p: number) => {
    const next = new URLSearchParams(params);
    next.set('page', String(p));
    setParams(next);
  };

  return (
    <>
      <PageHeader
        title="Notes"
        subtitle="Review generated summaries before they become final."
        actions={
          <Link to="/notes/new" className="btn btn-primary">
            <PlusCircle className="h-4 w-4" aria-hidden="true" /> New note
          </Link>
        }
      />

      <div role="group" aria-label="Filter by status" className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            aria-pressed={status === f.value}
            onClick={() => setFilter(f.value)}
            className={`btn !min-h-10 rounded-full border ${
              status === f.value
                ? 'border-primary bg-primary text-on-primary'
                : 'border-line bg-surface hover:bg-surface-2'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isPending ? (
        <PageLoading label="Loading notes" />
      ) : isError ? (
        <ErrorState message={error.message} onRetry={() => void refetch()} />
      ) : data.items.length === 0 ? (
        <EmptyState title={status ? 'No notes with this status' : 'No notes yet'}>
          {status ? (
            <button type="button" className="btn btn-secondary mt-2" onClick={() => setFilter(null)}>
              Show all notes
            </button>
          ) : (
            <>
              <p>Submit your first note to see a structured summary.</p>
              <Link to="/notes/new" className="btn btn-primary mt-4">
                <PlusCircle className="h-4 w-4" aria-hidden="true" /> New note
              </Link>
            </>
          )}
        </EmptyState>
      ) : (
        <>
          <ul className={`card divide-y divide-line overflow-hidden ${isPlaceholderData ? 'opacity-60' : ''}`}>
            {data.items.map((n) => (
              <li key={n.id}>
                <Link
                  to={`/notes/${n.id}`}
                  className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-4 transition-colors duration-150 hover:bg-surface-2 sm:px-5"
                >
                  <div className="min-w-0">
                    <div className="truncate font-semibold">{n.title || 'Untitled note'}</div>
                    <div className="text-sm text-muted">
                      {formatDateTime(n.created_at)} · {LANG[n.language]}
                      {n.generation > 1 ? ` · regenerated ×${n.generation - 1}` : ''}
                    </div>
                  </div>
                  <StatusBadge status={n.status} />
                </Link>
              </li>
            ))}
          </ul>
          <nav aria-label="Pagination" className="mt-4 flex items-center justify-between text-sm text-muted">
            <span>
              {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + data.items.length} of {data.total}
            </span>
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
                disabled={(page + 1) * PAGE_SIZE >= data.total}
                onClick={() => setPage(page + 1)}
              >
                Next <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </nav>
        </>
      )}
    </>
  );
}
