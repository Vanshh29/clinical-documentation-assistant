import { AlertTriangle, CheckCircle2, CircleDot, Clock, Loader2, XCircle } from 'lucide-react';
import type { ComponentType } from 'react';
import type { ConfidenceLevel } from '@/lib/summary';
import type { NoteStatus } from '@/lib/types';

const STATUS: Record<
  NoteStatus,
  {
    label: string;
    tone: string;
    Icon: ComponentType<{ className?: string }>;
    spin?: boolean;
  }
> = {
  SUBMITTED: { label: 'Queued', tone: 'bg-info-soft text-info', Icon: Clock },
  PROCESSING: {
    label: 'Processing',
    tone: 'bg-info-soft text-info',
    Icon: Loader2,
    spin: true,
  },
  PENDING_REVIEW: {
    label: 'Needs review',
    tone: 'bg-warning-soft text-warning',
    Icon: CircleDot,
  },
  APPROVED: {
    label: 'Approved',
    tone: 'bg-success-soft text-success',
    Icon: CheckCircle2,
  },
  REJECTED: {
    label: 'Rejected',
    tone: 'bg-surface-2 text-muted',
    Icon: XCircle,
  },
  FAILED_VALIDATION: {
    label: 'Failed',
    tone: 'bg-danger-soft text-danger',
    Icon: AlertTriangle,
  },
};

export const STATUS_LABEL = (s: NoteStatus): string => STATUS[s].label;

export function StatusBadge({ status }: { status: NoteStatus }) {
  const { label, tone, Icon, spin } = STATUS[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      <Icon className={`h-3.5 w-3.5 ${spin ? 'animate-spin motion-reduce:animate-none' : ''}`} aria-hidden="true" />
      {label}
    </span>
  );
}

const CONFIDENCE: Record<ConfidenceLevel, { label: string; tone: string }> = {
  high: { label: 'High confidence', tone: 'bg-success-soft text-success' },
  medium: { label: 'Medium confidence', tone: 'bg-warning-soft text-warning' },
  low: { label: 'Low confidence', tone: 'bg-danger-soft text-danger' },
  none: { label: 'Not documented', tone: 'bg-surface-2 text-muted' },
};

export function ConfidenceBadge({ level, value }: { level: ConfidenceLevel; value?: number }) {
  const { label, tone } = CONFIDENCE[level];
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>
      {label}
      {level !== 'none' && value !== undefined ? ` · ${Math.round(value * 100)}%` : ''}
    </span>
  );
}
