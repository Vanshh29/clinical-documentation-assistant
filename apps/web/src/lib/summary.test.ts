import { summaryFixture } from '@/test/utils';
import {
  clinicalSummarySchema,
  confidenceLevel,
  countChangedFields,
  parseSummary,
  summaryFormSchema,
  toFormValues,
  toPayload,
} from './summary';

describe('summary conversion', () => {
  it('parses a valid summary and rejects unknown shapes', () => {
    expect(parseSummary(summaryFixture())).not.toBeNull();
    expect(parseSummary({ nope: true })).toBeNull();
    expect(parseSummary(null)).toBeNull();
  });

  it('round-trips untouched form values to an identical payload', () => {
    const base = summaryFixture();
    expect(toPayload(base, toFormValues(base))).toEqual(base);
    expect(countChangedFields(base, toFormValues(base))).toBe(0);
  });

  it('turns a cleared field into "not documented" with no sources', () => {
    const base = summaryFixture();
    const values = { ...toFormValues(base), plan: '   ' };
    const payload = toPayload(base, values);
    expect(payload.plan).toEqual({ value: null, confidence: 0, source_spans: [] });
    expect(countChangedFields(base, values)).toBe(1);
  });

  it('gives a field filled in from nothing no confidence and no spans', () => {
    const base = summaryFixture();
    const payload = toPayload(base, { ...toFormValues(base), assessment: 'Viral infection' });
    expect(payload.assessment).toEqual({ value: 'Viral infection', confidence: 0, source_spans: [] });
  });

  it('keeps sources when an existing value is edited, and cleans list rows', () => {
    const base = summaryFixture();
    const values = toFormValues(base);
    values.medications = [{ name: ' ramipril ', dose: '10 mg', frequency: '' }];
    const payload = toPayload(base, values);
    expect(payload.medications.value).toEqual([{ name: 'ramipril', dose: '10 mg', frequency: null }]);
    expect(payload.medications.source_spans).toHaveLength(1);
  });

  it('produces payloads the summary schema accepts', () => {
    const base = summaryFixture();
    const values = { ...toFormValues(base), follow_up_items: [{ text: 'Recheck in 2 weeks' }], allergies: [] };
    expect(clinicalSummarySchema.safeParse(toPayload(base, values)).success).toBe(true);
  });

  it('validates form rows', () => {
    const base = toFormValues(summaryFixture());
    const bad = summaryFormSchema.safeParse({ ...base, medications: [{ name: ' ', dose: '', frequency: '' }] });
    expect(bad.success).toBe(false);
  });

  it('maps confidence to labelled levels', () => {
    expect(confidenceLevel(false, 0.9)).toBe('none');
    expect(confidenceLevel(true, 0.8)).toBe('high');
    expect(confidenceLevel(true, 0.5)).toBe('medium');
    expect(confidenceLevel(true, 0.49)).toBe('low');
  });
});
