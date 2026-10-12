import { zodResolver } from '@hookform/resolvers/zod';
import { AlertTriangle, ArrowLeft, Check, CheckCircle2, Loader2, RefreshCw, Save, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { Link, useParams } from 'react-router-dom';
import { Dialog } from '@/components/Dialog';
import { ErrorState, PageLoading } from '@/components/feedback';
import { StatusBadge } from '@/components/StatusBadge';
import { useToast } from '@/components/Toast';
import { ApiError } from '@/lib/api';
import { FAILURE_MESSAGES, formatDateTime, formatPercent } from '@/lib/format';
import { useApprove, useNote, useRegenerate, useReject, useSaveSummary } from '@/lib/queries';
import {
  countChangedFields,
  FIELD_LABELS,
  parseSummary,
  summaryFormSchema,
  toFormValues,
  toPayload,
  type ClinicalSummary,
  type SummaryFieldName,
  type SummaryFormValues,
} from '@/lib/summary';
import type { NoteDetail } from '@/lib/types';
import { NoteViewer } from './NoteViewer';
import { SummaryEditor } from './SummaryEditor';

const STEPS = ['Queued', 'Processing', 'Ready for review'] as const;

function Progress({ status }: { status: NoteDetail['status'] }) {
  const current = status === 'SUBMITTED' ? 0 : 1;
  return (
    <div role="status" aria-live="polite" className="card p-6">
      <div className="mb-4 flex items-center gap-3">
        <Loader2 className="h-5 w-5 animate-spin text-primary motion-reduce:animate-none" aria-hidden="true" />
        <p className="font-semibold">{status === 'SUBMITTED' ? 'Waiting for a worker…' : 'Preparing your summary…'}</p>
      </div>
      <ol className="space-y-2">
        {STEPS.map((s, i) => (
          <li key={s} className={`flex items-center gap-2 text-sm ${i <= current ? 'font-semibold' : 'text-muted'}`}>
            {i < current ? (
              <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
            ) : (
              <span
                className={`h-2.5 w-2.5 rounded-full ${i === current ? 'bg-primary' : 'bg-line'}`}
                aria-hidden="true"
              />
            )}
            {s}
            {i === current && <span className="sr-only"> (current step)</span>}
          </li>
        ))}
      </ol>
      <p className="mt-4 text-sm text-muted">
        Personal details are removed before the model reads your note. This page updates by itself.
      </p>
    </div>
  );
}

function Workspace({ note, base }: { note: NoteDetail; base: ClinicalSummary }) {
  const toast = useToast();
  const summary = note.summary!;
  const readOnly = note.status !== 'PENDING_REVIEW';
  const finalContent = readOnly
    ? (parseSummary(summary.approved_content) ?? base)
    : (parseSummary(summary.edited_content) ?? base);
  const initial = useMemo(() => toFormValues(finalContent), [finalContent]);

  const form = useForm<SummaryFormValues>({
    resolver: zodResolver(summaryFormSchema),
    defaultValues: initial,
  });
  const { isDirty } = form.formState;
  const [active, setActive] = useState<SummaryFieldName | null>(null);
  const [dialog, setDialog] = useState<'approve' | 'reject' | 'regenerate' | null>(null);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState<string | null>(null);

  const save = useSaveSummary(note.id);
  const approve = useApprove(note.id);
  const reject = useReject(note.id);
  const regenerate = useRegenerate(note.id);
  const busy = save.isPending || approve.isPending || reject.isPending || regenerate.isPending;

  useEffect(() => {
    form.reset(initial);
  }, [initial, form]);

  useEffect(() => {
    if (!isDirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [isDirty]);

  const ranges = active ? base[active].source_spans : [];
  const fail = (e: unknown) =>
    toast(e instanceof ApiError || e instanceof Error ? e.message : 'Something went wrong.', 'error');

  const saveDraft = form.handleSubmit(async (values) => {
    try {
      await save.mutateAsync(toPayload(base, values));
      toast('Draft saved');
    } catch (e) {
      fail(e);
    }
  });

  const confirmApprove = async () => {
    try {
      if (isDirty) await save.mutateAsync(toPayload(base, form.getValues()));
      await approve.mutateAsync();
      setDialog(null);
      toast('Summary approved');
    } catch (e) {
      setDialog(null);
      fail(e);
    }
  };

  const openApprove = async () => {
    // shouldFocus moves keyboard and screen-reader focus to the first invalid field.
    if (await form.trigger(undefined, { shouldFocus: true })) setDialog('approve');
    else toast('Fix the highlighted fields before approving.', 'error');
  };

  const confirmReject = async () => {
    if (reason.trim().length < 3) return setReasonError('Enter a reason (at least 3 characters)');
    try {
      await reject.mutateAsync(reason.trim());
      setDialog(null);
      toast('Summary rejected');
    } catch (e) {
      fail(e);
    }
  };

  const confirmRegenerate = async () => {
    try {
      await regenerate.mutateAsync();
      setDialog(null);
      toast('Regeneration requested');
    } catch (e) {
      setDialog(null);
      fail(e);
    }
  };

  const current = useWatch({ control: form.control }) as SummaryFormValues;
  const changed = countChangedFields(base, current);
  const diff = summary.diff;

  return (
    <>
      {note.status === 'APPROVED' && (
        <div
          role="status"
          className="mb-4 flex items-start gap-3 rounded-lg border border-success/40 bg-success-soft p-4 text-success"
        >
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <div>
            <p className="font-bold">Approved — this summary is final</p>
            <p className="text-sm">
              {summary.reviewed_at ? `Approved ${formatDateTime(summary.reviewed_at)}. ` : ''}
              {diff
                ? Object.keys(diff.changed_fields).length === 0
                  ? 'Approved without edits.'
                  : `${Object.keys(diff.changed_fields).length} field(s) edited (${formatPercent(diff.edit_ratio)} of content changed).`
                : ''}
            </p>
          </div>
        </div>
      )}
      {note.status === 'REJECTED' && (
        <div role="status" className="mb-4 flex items-start gap-3 rounded-lg border border-line bg-surface-2 p-4">
          <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-muted" aria-hidden="true" />
          <div>
            <p className="font-bold">Rejected</p>
            <p className="text-sm text-muted">Reason: {summary.rejection_reason}</p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <div className="lg:sticky lg:top-24">
          <NoteViewer body={note.body} ranges={ranges} activeLabel={active ? FIELD_LABELS[active] : null} />
        </div>
        <div>
          <SummaryEditor form={form} base={base} readOnly={readOnly} active={active} onActivate={setActive} />
          <p className="mt-3 text-xs text-muted">
            Model: {summary.model} · prompt {summary.prompt_version} · schema {summary.schema_version}. Always check
            against the original note.
          </p>
        </div>
      </div>

      {!readOnly && (
        <div className="sticky bottom-0 z-20 -mx-4 mt-6 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted" aria-live="polite">
              {isDirty ? `Unsaved changes in ${changed} field(s)` : 'No unsaved changes'}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={busy}
                onClick={() => setDialog('regenerate')}
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" /> Regenerate
              </button>
              <button type="button" className="btn btn-danger" disabled={busy} onClick={() => setDialog('reject')}>
                <XCircle className="h-4 w-4" aria-hidden="true" /> Reject
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={busy || !isDirty}
                onClick={() => void saveDraft()}
              >
                <Save className="h-4 w-4" aria-hidden="true" /> {save.isPending ? 'Saving…' : 'Save draft'}
              </button>
              <button type="button" className="btn btn-success" disabled={busy} onClick={() => void openApprove()}>
                <Check className="h-4 w-4" aria-hidden="true" /> Approve
              </button>
            </div>
          </div>
        </div>
      )}

      <Dialog open={dialog === 'approve'} onClose={() => setDialog(null)} title="Approve this summary?">
        <p className="text-sm text-muted">
          Approving makes the summary final and records your edits
          {isDirty ? ` (${changed} field(s) changed from the generated version)` : ' (none: approved as generated)'}.
          This cannot be undone.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => setDialog(null)}>
            Keep reviewing
          </button>
          <button type="button" className="btn btn-success" disabled={busy} onClick={() => void confirmApprove()}>
            {approve.isPending || save.isPending ? 'Approving…' : 'Approve summary'}
          </button>
        </div>
      </Dialog>

      <Dialog open={dialog === 'reject'} onClose={() => setDialog(null)} title="Reject this summary">
        <label htmlFor="reject-reason" className="label">
          Reason
        </label>
        <textarea
          id="reject-reason"
          rows={3}
          className="input"
          value={reason}
          aria-invalid={!!reasonError}
          onChange={(e) => {
            setReason(e.target.value);
            setReasonError(null);
          }}
        />
        {reasonError ? (
          <p className="error-text">{reasonError}</p>
        ) : (
          <p className="hint">Do not include patient details.</p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => setDialog(null)}>
            Cancel
          </button>
          <button type="button" className="btn btn-danger" disabled={busy} onClick={() => void confirmReject()}>
            {reject.isPending ? 'Rejecting…' : 'Reject summary'}
          </button>
        </div>
      </Dialog>

      <Dialog open={dialog === 'regenerate'} onClose={() => setDialog(null)} title="Generate a new summary?">
        <p className="text-sm text-muted">
          The note is processed again and the current summary is replaced for review.
          {isDirty ? ' Your unsaved edits will be lost.' : ''}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => setDialog(null)}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void confirmRegenerate()}>
            {regenerate.isPending ? 'Requesting…' : 'Regenerate'}
          </button>
        </div>
      </Dialog>
    </>
  );
}

export function ReviewPage() {
  const { id = '' } = useParams();
  const { data: note, isPending, isError, error, refetch } = useNote(id);
  const regenerate = useRegenerate(id);
  const toast = useToast();

  if (isPending) return <PageLoading label="Loading note" />;
  if (isError)
    return (
      <ErrorState
        message={
          error instanceof ApiError && error.status === 404
            ? 'This note does not exist or you do not have access to it.'
            : error.message
        }
        onRetry={() => void refetch()}
      />
    );

  const base = parseSummary(note.summary?.content);
  const inProgress = note.status === 'SUBMITTED' || note.status === 'PROCESSING';

  return (
    <>
      <Link
        to="/"
        className="mb-3 inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> All notes
      </Link>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{note.title || 'Untitled note'}</h1>
          <p className="text-sm text-muted">
            Submitted {formatDateTime(note.created_at)}
            {note.generation > 1 ? ` · generation ${note.generation}` : ''}
          </p>
        </div>
        <StatusBadge status={note.status} />
      </div>

      {inProgress && (
        <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
          <NoteViewer body={note.body} ranges={[]} activeLabel={null} />
          <Progress status={note.status} />
        </div>
      )}

      {note.status === 'FAILED_VALIDATION' && (
        <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
          <NoteViewer body={note.body} ranges={[]} activeLabel={null} />
          <div role="alert" className="card p-6">
            <div className="mb-2 flex items-center gap-2 text-danger">
              <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              <h2 className="text-lg font-bold">A summary could not be produced</h2>
            </div>
            <p className="text-muted">
              {FAILURE_MESSAGES[note.failure_reason ?? ''] ?? FAILURE_MESSAGES.internal_error}
            </p>
            <button
              type="button"
              className="btn btn-primary mt-4"
              disabled={regenerate.isPending}
              onClick={() =>
                regenerate.mutate(undefined, {
                  onError: (e) => toast(e.message, 'error'),
                })
              }
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" /> {regenerate.isPending ? 'Retrying…' : 'Try again'}
            </button>
          </div>
        </div>
      )}

      {(note.status === 'PENDING_REVIEW' || note.status === 'APPROVED' || note.status === 'REJECTED') &&
        (base && note.summary ? (
          <Workspace key={`${note.id}-${note.generation}-${note.status}`} note={note} base={base} />
        ) : (
          <ErrorState message="This summary is in an unexpected format and cannot be displayed." />
        ))}
    </>
  );
}
