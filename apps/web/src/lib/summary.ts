import { z } from 'zod';

export const SUMMARY_FIELDS = [
  'chief_complaint',
  'history_of_present_illness',
  'medications',
  'allergies',
  'assessment',
  'plan',
  'follow_up_items',
] as const;
export type SummaryFieldName = (typeof SUMMARY_FIELDS)[number];

export const FIELD_LABELS: Record<SummaryFieldName, string> = {
  chief_complaint: 'Chief complaint',
  history_of_present_illness: 'History of present illness',
  medications: 'Medications mentioned',
  allergies: 'Allergies mentioned',
  assessment: 'Assessment',
  plan: 'Plan',
  follow_up_items: 'Follow-up items',
};

const span = z.object({
  start: z.number().int().min(0),
  end: z.number().int().positive(),
  text: z.string(),
});
export type Span = z.infer<typeof span>;

const medication = z.object({
  name: z.string(),
  dose: z.string().nullable(),
  frequency: z.string().nullable(),
});
export type Medication = z.infer<typeof medication>;

const field = <T extends z.ZodType>(value: T) =>
  z.object({
    value: value.nullable(),
    confidence: z.number().min(0).max(1),
    source_spans: z.array(span),
  });

export const clinicalSummarySchema = z.object({
  schema_version: z.literal('1.0'),
  chief_complaint: field(z.string()),
  history_of_present_illness: field(z.string()),
  medications: field(z.array(medication)),
  allergies: field(z.array(z.string())),
  assessment: field(z.string()),
  plan: field(z.string()),
  follow_up_items: field(z.array(z.string())),
});
export type ClinicalSummary = z.infer<typeof clinicalSummarySchema>;

/** Values the clinician edits. List items are objects so react-hook-form can track rows. */
export const summaryFormSchema = z.object({
  chief_complaint: z.string().max(5000, 'Keep this under 5,000 characters'),
  history_of_present_illness: z.string().max(5000, 'Keep this under 5,000 characters'),
  assessment: z.string().max(5000, 'Keep this under 5,000 characters'),
  plan: z.string().max(5000, 'Keep this under 5,000 characters'),
  medications: z.array(
    z.object({
      name: z.string().trim().min(1, 'Enter the medication name'),
      dose: z.string(),
      frequency: z.string(),
    }),
  ),
  allergies: z.array(
    z.object({
      text: z.string().trim().min(1, 'Enter an allergy or remove this row'),
    }),
  ),
  follow_up_items: z.array(
    z.object({
      text: z.string().trim().min(1, 'Enter a follow-up or remove this row'),
    }),
  ),
});
export type SummaryFormValues = z.infer<typeof summaryFormSchema>;

export function parseSummary(raw: unknown): ClinicalSummary | null {
  const result = clinicalSummarySchema.safeParse(raw);
  return result.success ? result.data : null;
}

export function toFormValues(s: ClinicalSummary): SummaryFormValues {
  return {
    chief_complaint: s.chief_complaint.value ?? '',
    history_of_present_illness: s.history_of_present_illness.value ?? '',
    assessment: s.assessment.value ?? '',
    plan: s.plan.value ?? '',
    medications: (s.medications.value ?? []).map((m) => ({
      name: m.name,
      dose: m.dose ?? '',
      frequency: m.frequency ?? '',
    })),
    allergies: (s.allergies.value ?? []).map((text) => ({ text })),
    follow_up_items: (s.follow_up_items.value ?? []).map((text) => ({ text })),
  };
}

/**
 * Build the payload the API validates. A field the clinician clears becomes "not documented"
 * (null, no spans); a field they fill in from nothing carries no source spans or confidence.
 */
export function toPayload(base: ClinicalSummary, v: SummaryFormValues): ClinicalSummary {
  const text = (name: 'chief_complaint' | 'history_of_present_illness' | 'assessment' | 'plan') => {
    const value = v[name].trim();
    const prior = base[name];
    return value
      ? {
          value,
          confidence: prior.value ? prior.confidence : 0,
          source_spans: prior.value ? prior.source_spans : [],
        }
      : { value: null, confidence: 0, source_spans: [] };
  };
  const list = <T>(name: 'medications' | 'allergies' | 'follow_up_items', items: T[]) => {
    const prior = base[name];
    return items.length
      ? {
          value: items,
          confidence: prior.value ? prior.confidence : 0,
          source_spans: prior.value ? prior.source_spans : [],
        }
      : { value: null, confidence: 0, source_spans: [] };
  };
  return {
    schema_version: '1.0',
    chief_complaint: text('chief_complaint'),
    history_of_present_illness: text('history_of_present_illness'),
    assessment: text('assessment'),
    plan: text('plan'),
    medications: list(
      'medications',
      v.medications.map((m) => ({
        name: m.name.trim(),
        dose: m.dose.trim() || null,
        frequency: m.frequency.trim() || null,
      })),
    ),
    allergies: list(
      'allergies',
      v.allergies.map((a) => a.text.trim()),
    ),
    follow_up_items: list(
      'follow_up_items',
      v.follow_up_items.map((a) => a.text.trim()),
    ),
  };
}

export function countChangedFields(base: ClinicalSummary, v: SummaryFormValues): number {
  const next = toPayload(base, v);
  return SUMMARY_FIELDS.filter((n) => JSON.stringify(base[n].value) !== JSON.stringify(next[n].value)).length;
}

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'none';
export function confidenceLevel(documented: boolean, c: number): ConfidenceLevel {
  if (!documented) return 'none';
  return c >= 0.8 ? 'high' : c >= 0.5 ? 'medium' : 'low';
}
