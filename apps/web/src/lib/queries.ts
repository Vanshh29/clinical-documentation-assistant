import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import type { ClinicalSummary } from './summary';
import type { AuditPage, Metrics, NoteDetail, NoteItem, NoteList, NoteStatus, SummaryRecord } from './types';

const IN_PROGRESS: NoteStatus[] = ['SUBMITTED', 'PROCESSING'];
export const isInProgress = (s: NoteStatus | undefined): boolean => !!s && IN_PROGRESS.includes(s);

export const PAGE_SIZE = 20;

export function useNotes(status: NoteStatus | null, page: number) {
  return useQuery({
    queryKey: ['notes', status, page],
    queryFn: () => {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(page * PAGE_SIZE),
      });
      if (status) params.set('status', status);
      return api<NoteList>(`/notes?${params}`);
    },
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (q.state.data?.items.some((n) => isInProgress(n.status)) ? 3000 : false),
  });
}

export function useNote(id: string) {
  return useQuery({
    queryKey: ['note', id],
    queryFn: () => api<NoteDetail>(`/notes/${id}`),
    refetchInterval: (q) => (isInProgress(q.state.data?.status) ? 1500 : false),
  });
}

export interface NewNote {
  body: string;
  title?: string;
  language: 'auto' | 'de' | 'en';
  source: 'paste' | 'upload';
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (note: NewNote) => api<NoteItem>('/notes', { method: 'POST', json: note }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  });
}

function useNoteAction<TVars, TOut>(id: string, run: (v: TVars) => Promise<TOut>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['note', id] });
      await qc.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}

export const useSaveSummary = (id: string) =>
  useNoteAction(id, (summary: ClinicalSummary) =>
    api<SummaryRecord>(`/notes/${id}/summary`, {
      method: 'PUT',
      json: summary,
    }),
  );
export const useApprove = (id: string) =>
  useNoteAction(id, (_: void) => api<SummaryRecord>(`/notes/${id}/approve`, { method: 'POST' }));
export const useReject = (id: string) =>
  useNoteAction(id, (reason: string) =>
    api<SummaryRecord>(`/notes/${id}/reject`, {
      method: 'POST',
      json: { reason },
    }),
  );
export const useRegenerate = (id: string) =>
  useNoteAction(id, (_: void) => api<NoteItem>(`/notes/${id}/regenerate`, { method: 'POST' }));

export const useMetrics = () =>
  useQuery({
    queryKey: ['metrics'],
    queryFn: () => api<Metrics>('/admin/metrics'),
  });

export function useAudit(action: string, page: number) {
  return useQuery({
    queryKey: ['audit', action, page],
    queryFn: () => {
      const params = new URLSearchParams({
        limit: '25',
        offset: String(page * 25),
      });
      if (action) params.set('action', action);
      return api<AuditPage>(`/admin/audit?${params}`);
    },
    placeholderData: keepPreviousData,
  });
}

export function useEraseMyData() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ notes_deleted: number }>('/me/data', { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries(),
  });
}
