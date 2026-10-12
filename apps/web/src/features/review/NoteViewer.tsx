import { useEffect, useMemo, useRef } from 'react';
import { segments, type Range } from '@/lib/highlight';

interface Props {
  body: string;
  ranges: Range[];
  /** Name of the field whose evidence is highlighted, for assistive technology. */
  activeLabel: string | null;
}

export function NoteViewer({ body, ranges, activeLabel }: Props) {
  const parts = useMemo(() => segments(body, ranges), [body, ranges]);
  const scroller = useRef<HTMLDivElement | null>(null);
  const firstMark = useRef<HTMLElement | null>(null);

  // Scroll only the note panel, never the page, so the header and banner stay put.
  useEffect(() => {
    const box = scroller.current;
    const mark = firstMark.current;
    if (!box || !mark) return;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    box.scrollTo({ top: Math.max(0, mark.offsetTop - box.clientHeight / 3), behavior: reduce ? 'auto' : 'smooth' });
  }, [parts]);

  const highlighted = parts.filter((p) => p.highlighted).length;
  return (
    <section aria-labelledby="original-note-title" className="card flex min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 id="original-note-title" className="text-base font-bold">
          Original note
        </h2>
        <p className="text-xs text-muted" aria-live="polite">
          {activeLabel
            ? highlighted > 0
              ? `Showing evidence for ${activeLabel}`
              : `No source text for ${activeLabel}`
            : 'Select a field to see its source'}
        </p>
      </div>
      <div
        ref={scroller}
        tabIndex={0}
        role="region"
        aria-label="Note text"
        className="max-h-72 overflow-auto whitespace-pre-wrap break-words px-4 py-4 font-mono text-sm leading-relaxed lg:max-h-[calc(100vh-14rem)]"
      >
        {parts.map((p, i) =>
          p.highlighted ? (
            <mark
              key={i}
              ref={p.first ? (el) => void (firstMark.current = el) : undefined}
              className="rounded bg-mark/50 px-0.5 text-fg"
            >
              {p.text}
            </mark>
          ) : (
            <span key={i}>{p.text}</span>
          ),
        )}
      </div>
    </section>
  );
}
