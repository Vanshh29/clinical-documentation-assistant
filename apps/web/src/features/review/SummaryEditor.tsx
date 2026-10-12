import { Eye, Plus, Trash2 } from 'lucide-react';
import type { ReactNode } from 'react';
import { useFieldArray, useWatch, type UseFormReturn } from 'react-hook-form';
import { ConfidenceBadge } from '@/components/StatusBadge';
import {
  confidenceLevel,
  FIELD_LABELS,
  type ClinicalSummary,
  type SummaryFieldName,
  type SummaryFormValues,
} from '@/lib/summary';

interface Props {
  form: UseFormReturn<SummaryFormValues>;
  base: ClinicalSummary;
  readOnly: boolean;
  active: SummaryFieldName | null;
  onActivate: (name: SummaryFieldName) => void;
}

const NOT_DOCUMENTED = <span className="italic text-muted">Not documented in the note</span>;

function Card({
  name,
  base,
  active,
  onActivate,
  children,
}: {
  name: SummaryFieldName;
  base: ClinicalSummary;
  active: boolean;
  onActivate: (n: SummaryFieldName) => void;
  children: ReactNode;
}) {
  const f = base[name];
  const hasValue = Array.isArray(f.value) ? f.value.length > 0 : !!f.value;
  const hasSource = f.source_spans.length > 0;
  // An empty list that cites a sentence means the note says there are none, not that it is silent.
  const statedNone = Array.isArray(f.value) && f.value.length === 0 && hasSource;
  return (
    <section
      aria-labelledby={`${name}-label`}
      onFocusCapture={() => onActivate(name)}
      onMouseEnter={() => onActivate(name)}
      className={`card p-4 transition-shadow duration-150 ${active ? 'ring-2 ring-primary' : ''}`}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 id={`${name}-label`} className="text-sm font-bold">
            {FIELD_LABELS[name]}
          </h3>
          {statedNone ? (
            <span className="inline-flex items-center rounded-full bg-surface-2 px-2 py-0.5 text-xs font-semibold text-muted">
              Stated as none
            </span>
          ) : (
            <ConfidenceBadge level={confidenceLevel(hasValue, f.confidence)} value={f.confidence} />
          )}
        </div>
        {hasSource && (
          <button
            type="button"
            aria-pressed={active}
            aria-label={`Show source for ${FIELD_LABELS[name]}`}
            onClick={() => onActivate(name)}
            className="btn btn-ghost !min-h-9 text-primary"
          >
            <Eye className="h-4 w-4" aria-hidden="true" /> Source
          </button>
        )}
      </div>
      {children}
    </section>
  );
}

function TextField({
  name,
  form,
  readOnly,
}: {
  name: 'chief_complaint' | 'history_of_present_illness' | 'assessment' | 'plan';
  form: UseFormReturn<SummaryFormValues>;
  readOnly: boolean;
}) {
  const value = useWatch({ control: form.control, name });
  const error = form.formState.errors[name];
  if (readOnly) return <p className="whitespace-pre-wrap">{value || NOT_DOCUMENTED}</p>;
  return (
    <>
      <textarea
        rows={3}
        className="input"
        aria-labelledby={`${name}-label`}
        aria-invalid={!!error}
        placeholder="Not documented in the note"
        {...form.register(name)}
      />
      {error && <p className="error-text">{error.message}</p>}
    </>
  );
}

function StringList({
  name,
  form,
  readOnly,
  noun,
}: {
  name: 'allergies' | 'follow_up_items';
  form: UseFormReturn<SummaryFormValues>;
  readOnly: boolean;
  noun: string;
}) {
  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name,
  });
  const errors = form.formState.errors[name];
  if (readOnly)
    return fields.length === 0 ? (
      <p>{NOT_DOCUMENTED}</p>
    ) : (
      <ul className="list-disc space-y-1 pl-5">
        {fields.map((f, i) => (
          <li key={f.id}>{form.getValues(`${name}.${i}.text`)}</li>
        ))}
      </ul>
    );
  return (
    <div className="space-y-2">
      {fields.length === 0 && <p>{NOT_DOCUMENTED}</p>}
      {fields.map((f, i) => (
        <div key={f.id}>
          <div className="flex gap-2">
            <input
              className="input"
              aria-label={`${noun} ${i + 1}`}
              aria-invalid={!!errors?.[i]?.text}
              {...form.register(`${name}.${i}.text`)}
            />
            <button
              type="button"
              className="btn btn-ghost shrink-0 !px-3"
              aria-label={`Remove ${noun} ${i + 1}`}
              onClick={() => remove(i)}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          {errors?.[i]?.text && <p className="error-text">{errors[i]?.text?.message}</p>}
        </div>
      ))}
      <button type="button" className="btn btn-secondary" onClick={() => append({ text: '' })}>
        <Plus className="h-4 w-4" aria-hidden="true" /> Add {noun}
      </button>
    </div>
  );
}

function Medications({ form, readOnly }: { form: UseFormReturn<SummaryFormValues>; readOnly: boolean }) {
  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: 'medications',
  });
  const errors = form.formState.errors.medications;
  if (readOnly)
    return fields.length === 0 ? (
      <p>{NOT_DOCUMENTED}</p>
    ) : (
      <ul className="space-y-1">
        {fields.map((f, i) => {
          const m = form.getValues(`medications.${i}`);
          return (
            <li key={f.id}>
              <span className="font-semibold">{m.name}</span>
              {[m.dose, m.frequency].filter(Boolean).length > 0 && (
                <span className="text-muted"> — {[m.dose, m.frequency].filter(Boolean).join(', ')}</span>
              )}
            </li>
          );
        })}
      </ul>
    );
  return (
    <div className="space-y-3">
      {fields.length === 0 && <p>{NOT_DOCUMENTED}</p>}
      {fields.map((f, i) => (
        <fieldset key={f.id} className="rounded-lg border border-line p-3">
          <legend className="px-1 text-xs font-semibold text-muted">Medication {i + 1}</legend>
          <div className="grid gap-2 sm:grid-cols-[2fr_1fr_1.4fr_auto]">
            <div>
              <label className="sr-only" htmlFor={`med-name-${i}`}>
                Medication {i + 1} name
              </label>
              <input
                id={`med-name-${i}`}
                className="input"
                placeholder="Name"
                aria-invalid={!!errors?.[i]?.name}
                {...form.register(`medications.${i}.name`)}
              />
            </div>
            <div>
              <label className="sr-only" htmlFor={`med-dose-${i}`}>
                Medication {i + 1} dose
              </label>
              <input
                id={`med-dose-${i}`}
                className="input"
                placeholder="Dose"
                {...form.register(`medications.${i}.dose`)}
              />
            </div>
            <div>
              <label className="sr-only" htmlFor={`med-freq-${i}`}>
                Medication {i + 1} frequency
              </label>
              <input
                id={`med-freq-${i}`}
                className="input"
                placeholder="Frequency"
                {...form.register(`medications.${i}.frequency`)}
              />
            </div>
            <button
              type="button"
              className="btn btn-ghost !px-3"
              aria-label={`Remove medication ${i + 1}`}
              onClick={() => remove(i)}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          {errors?.[i]?.name && <p className="error-text">{errors[i]?.name?.message}</p>}
        </fieldset>
      ))}
      <button type="button" className="btn btn-secondary" onClick={() => append({ name: '', dose: '', frequency: '' })}>
        <Plus className="h-4 w-4" aria-hidden="true" /> Add medication
      </button>
    </div>
  );
}

export function SummaryEditor({ form, base, readOnly, active, onActivate }: Props) {
  const card = (name: SummaryFieldName, body: ReactNode) => (
    <Card key={name} name={name} base={base} active={active === name} onActivate={onActivate}>
      {body}
    </Card>
  );
  return (
    <div className="space-y-4">
      {card('chief_complaint', <TextField name="chief_complaint" form={form} readOnly={readOnly} />)}
      {card(
        'history_of_present_illness',
        <TextField name="history_of_present_illness" form={form} readOnly={readOnly} />,
      )}
      {card('medications', <Medications form={form} readOnly={readOnly} />)}
      {card('allergies', <StringList name="allergies" form={form} readOnly={readOnly} noun="allergy" />)}
      {card('assessment', <TextField name="assessment" form={form} readOnly={readOnly} />)}
      {card('plan', <TextField name="plan" form={form} readOnly={readOnly} />)}
      {card('follow_up_items', <StringList name="follow_up_items" form={form} readOnly={readOnly} noun="follow-up" />)}
    </div>
  );
}
