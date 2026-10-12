const date = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : date.format(d);
}

export function formatPercent(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined ? '—' : `${(v * 100).toFixed(digits)}%`;
}

export function formatMs(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`;
}

export function formatSeconds(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return v < 10 ? `${v.toFixed(1)} s` : `${Math.round(v)} s`;
}

export function formatUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return v > 0 && v < 0.01 ? `<$0.01` : `$${v.toFixed(2)}`;
}

export function formatNumber(v: number): string {
  return new Intl.NumberFormat().format(v);
}

export const FAILURE_MESSAGES: Record<string, string> = {
  schema_validation_failed: 'The model did not return a summary that passed validation after several attempts.',
  llm_unavailable: 'The language model service was not reachable. Nothing is wrong with your note.',
  llm_request_rejected: 'The language model service rejected the request.',
  worker_timeout: 'Processing took too long and was stopped.',
  internal_error: 'Something went wrong while processing this note.',
};
