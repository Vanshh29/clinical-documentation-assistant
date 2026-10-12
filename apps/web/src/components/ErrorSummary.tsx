import { forwardRef } from 'react';

export interface ErrorItem {
  field: string;
  message: string;
}

/** Focusable summary of form errors; each item links to its field (WCAG error identification). */
export const ErrorSummary = forwardRef<HTMLDivElement, { errors: ErrorItem[] }>(function ErrorSummary({ errors }, ref) {
  if (errors.length === 0) return null;
  return (
    <div
      ref={ref}
      role="alert"
      tabIndex={-1}
      aria-labelledby="error-summary-title"
      className="mb-5 rounded-lg border border-danger/40 bg-danger-soft p-4"
    >
      <h2 id="error-summary-title" className="font-bold text-danger">
        There is a problem
      </h2>
      <ul className="mt-1 list-disc pl-5 text-sm">
        {errors.map((e) => (
          <li key={`${e.field}-${e.message}`}>
            <a href={`#${e.field}`} className="font-medium underline">
              {e.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
});
