export interface Range {
  start: number;
  end: number;
}

export interface Segment {
  text: string;
  highlighted: boolean;
  /** Index of the first highlighted segment, used to scroll it into view. */
  first?: boolean;
}

/** Split `body` into plain and highlighted segments. Out-of-range spans are clamped; overlaps merge. */
export function segments(body: string, ranges: Range[]): Segment[] {
  const clean = ranges
    .map((r) => ({
      start: Math.max(0, r.start),
      end: Math.min(body.length, r.end),
    }))
    .filter((r) => r.end > r.start)
    .sort((a, b) => a.start - b.start);
  const merged: Range[] = [];
  for (const r of clean) {
    const last = merged[merged.length - 1];
    if (last && r.start <= last.end) last.end = Math.max(last.end, r.end);
    else merged.push({ ...r });
  }
  const out: Segment[] = [];
  let cursor = 0;
  for (const r of merged) {
    if (r.start > cursor) out.push({ text: body.slice(cursor, r.start), highlighted: false });
    out.push({
      text: body.slice(r.start, r.end),
      highlighted: true,
      first: out.every((s) => !s.highlighted),
    });
    cursor = r.end;
  }
  if (cursor < body.length) out.push({ text: body.slice(cursor), highlighted: false });
  return out.length ? out : [{ text: body, highlighted: false }];
}
