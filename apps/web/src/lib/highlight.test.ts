import { segments } from './highlight';

describe('segments', () => {
  const body = 'Patient has a cough. Takes ibuprofen daily.';

  it('returns one plain segment without ranges', () => {
    expect(segments(body, [])).toEqual([{ text: body, highlighted: false }]);
  });

  it('splits into plain and highlighted parts that rebuild the text', () => {
    const parts = segments(body, [{ start: 14, end: 19 }]);
    expect(parts.map((p) => p.text).join('')).toBe(body);
    expect(parts.filter((p) => p.highlighted).map((p) => p.text)).toEqual(['cough']);
  });

  it('merges overlapping and touching ranges and marks only the first', () => {
    const parts = segments(body, [
      { start: 0, end: 7 },
      { start: 5, end: 11 },
      { start: 11, end: 14 },
    ]);
    const marked = parts.filter((p) => p.highlighted);
    expect(marked).toHaveLength(1);
    expect(marked[0]).toMatchObject({ text: 'Patient has a ', first: true });
  });

  it('clamps out-of-range spans and ignores empty ones', () => {
    const parts = segments(body, [
      { start: -5, end: 7 },
      { start: 40, end: 500 },
      { start: 10, end: 10 },
    ]);
    expect(parts.map((p) => p.text).join('')).toBe(body);
    expect(parts.filter((p) => p.highlighted).map((p) => p.text)).toEqual(['Patient', 'ly.']);
  });

  it('flags the first highlight even when it follows plain text', () => {
    const parts = segments(body, [
      { start: 21, end: 26 },
      { start: 0, end: 7 },
    ]);
    expect(parts.filter((p) => p.highlighted).map((p) => p.first)).toEqual([true, false]);
  });
});
