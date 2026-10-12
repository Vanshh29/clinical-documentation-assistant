export type Role = 'clinician' | 'admin';

export type NoteStatus = 'SUBMITTED' | 'PROCESSING' | 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED' | 'FAILED_VALIDATION';

export interface Me {
  id: string;
  email: string;
  role: Role;
  display_name: string;
}

export interface NoteItem {
  id: string;
  title: string | null;
  language: 'de' | 'en' | 'auto';
  source: 'paste' | 'upload';
  status: NoteStatus;
  failure_reason: string | null;
  generation: number;
  created_at: string;
  updated_at: string;
}

export interface NoteList {
  items: NoteItem[];
  total: number;
}

export interface SummaryRecord {
  id: string;
  generation: number;
  schema_version: string;
  model: string;
  prompt_version: string;
  content: unknown;
  edited_content: unknown | null;
  approved_content: unknown | null;
  diff: { changed_fields: Record<string, unknown>; edit_ratio: number } | null;
  rejection_reason: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface NoteDetail extends NoteItem {
  body: string;
  summary: SummaryRecord | null;
}

export interface Metrics {
  notes_total: number;
  notes_by_status: Record<string, number>;
  approval_rate: number | null;
  edit_rate: number | null;
  mean_edit_ratio: number | null;
  validation_failure_rate: number | null;
  llm_calls: number;
  llm_latency_ms_p50: number | null;
  llm_latency_ms_p95: number | null;
  time_to_summary_s_p50: number | null;
  time_to_summary_s_p95: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd_total: number;
  cost_usd_per_note: number | null;
}

export interface AuditEntry {
  id: number;
  occurred_at: string;
  actor_id: string | null;
  actor_role: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  request_id: string | null;
  model: string | null;
  prompt_version: string | null;
  schema_version: string | null;
  details: Record<string, unknown>;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
}
