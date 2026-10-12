import { zodResolver } from '@hookform/resolvers/zod';
import { FileUp, Send, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { ErrorSummary, type ErrorItem } from '@/components/ErrorSummary';
import { PageHeader } from '@/components/feedback';
import { useCreateNote } from '@/lib/queries';
import { SAMPLE_NOTES } from '@/lib/samples';

const MAX_CHARS = 50_000;
const MAX_FILE_BYTES = 200_000;

const schema = z.object({
  title: z.string().trim().max(200, 'Keep the title under 200 characters'),
  language: z.enum(['auto', 'de', 'en']),
  body: z
    .string()
    .trim()
    .min(20, 'Enter at least 20 characters of note text')
    .max(MAX_CHARS, `Keep the note under ${MAX_CHARS.toLocaleString()} characters`),
});
type Values = z.infer<typeof schema>;

export function NewNotePage() {
  const navigate = useNavigate();
  const create = useCreateNote();
  const [source, setSource] = useState<'paste' | 'upload'>('paste');
  const [fileError, setFileError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  const {
    register,
    handleSubmit,
    setValue,
    control,
    getValues,
    formState: { errors, isSubmitting, submitCount },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    shouldFocusError: false,
    defaultValues: { title: '', language: 'auto', body: '' },
  });

  const length = useWatch({ control, name: 'body' }).length;
  const errorItems: ErrorItem[] = [
    ...(errors.title ? [{ field: 'title', message: errors.title.message ?? '' }] : []),
    ...(errors.body ? [{ field: 'body', message: errors.body.message ?? '' }] : []),
    ...(serverError ? [{ field: 'body', message: serverError }] : []),
  ];

  useEffect(() => {
    if (errorItems.length > 0) summaryRef.current?.focus();
    // Move focus to the summary after each failed submit, not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submitCount, serverError]);

  const onFile = async (file: File | undefined) => {
    setFileError(null);
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) return setFileError('That file is larger than 200 KB. Use a shorter text file.');
    if (!/\.(txt|md|text)$/i.test(file.name) && !file.type.startsWith('text/'))
      return setFileError('Only plain text files (.txt) are supported.');
    setValue('body', await file.text(), {
      shouldValidate: true,
      shouldDirty: true,
    });
    if (!getValues('title')) setValue('title', file.name.replace(/\.[^.]+$/, ''));
    setSource('upload');
  };

  const onSubmit = handleSubmit(async (v) => {
    setServerError(null);
    try {
      const note = await create.mutateAsync({
        body: v.body,
        title: v.title || undefined,
        language: v.language,
        source,
      });
      navigate(`/notes/${note.id}`);
    } catch (e) {
      setServerError(e instanceof Error ? e.message : 'The note could not be submitted.');
    }
  });

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="New note"
        subtitle="Paste a clinical note or upload a text file. A structured summary is prepared for your review."
      />
      <ErrorSummary ref={summaryRef} errors={errorItems} />
      <form onSubmit={onSubmit} noValidate className="card space-y-5 p-5 sm:p-6">
        <div className="grid gap-5 sm:grid-cols-[1fr_12rem]">
          <div>
            <label htmlFor="title" className="label">
              Title <span className="font-normal text-muted">(optional)</span>
            </label>
            <input
              id="title"
              className="input"
              autoComplete="off"
              aria-invalid={!!errors.title}
              {...register('title')}
            />
          </div>
          <div>
            <label htmlFor="language" className="label">
              Language
            </label>
            <select id="language" className="input" {...register('language')}>
              <option value="auto">Detect automatically</option>
              <option value="de">German</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>

        <div>
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <label htmlFor="body" className="label !mb-0">
              Note text
            </label>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_NOTES.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  className="btn btn-ghost !min-h-9 text-primary"
                  onClick={() => {
                    setValue('body', s.body, { shouldValidate: true });
                    setValue('title', s.title);
                    setValue('language', s.language);
                    setSource('paste');
                  }}
                >
                  <Sparkles className="h-4 w-4" aria-hidden="true" /> {s.label}
                </button>
              ))}
            </div>
          </div>
          <textarea
            id="body"
            rows={14}
            className="input font-mono text-sm leading-relaxed"
            aria-invalid={!!errors.body}
            aria-describedby="body-hint"
            {...register('body', {
              onChange: () => setSource((s) => (s === 'upload' ? 'upload' : 'paste')),
            })}
          />
          <div id="body-hint" className="mt-1 flex flex-wrap justify-between gap-2 text-sm text-muted">
            <span>Use fictional text only. Personal details are removed before the language model sees the note.</span>
            <span aria-live="polite">
              {length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
            </span>
          </div>
        </div>

        <div>
          <label htmlFor="file" className="btn btn-secondary cursor-pointer">
            <FileUp className="h-4 w-4" aria-hidden="true" /> Upload a text file
          </label>
          <input
            id="file"
            type="file"
            accept=".txt,.md,text/plain"
            className="sr-only"
            onChange={(e) => {
              void onFile(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
          {fileError && (
            <p role="alert" className="error-text">
              {fileError}
            </p>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-line pt-4">
          <button type="button" className="btn btn-ghost" onClick={() => navigate(-1)}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            <Send className="h-4 w-4" aria-hidden="true" />
            {isSubmitting ? 'Submitting…' : 'Submit for summary'}
          </button>
        </div>
      </form>
    </div>
  );
}
