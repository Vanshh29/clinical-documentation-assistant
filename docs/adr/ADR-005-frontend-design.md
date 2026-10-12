# ADR-005: Frontend design decisions

- Status: Accepted
- Date: 2026-10-12

## Decisions
1. **Flat, bordered, high-contrast surfaces** rather than a soft or glossy style. The review screen is dense and read for long stretches; clear edges and strong contrast beat decoration. All colours are design tokens (CSS variables) with a light and a dark set; text/background pairs are at least 4.5:1 and the primary teal (`#0E7490`) carries white text at 5.4:1.
2. **Meaning is never colour alone.** Status and confidence badges pair an icon and a word with the colour; the status chart prints each label and count next to its bar.
3. **Source highlighting scrolls the note panel, not the page.** Using `scrollIntoView` moved the whole page and hid the header; the viewer now scrolls its own container.
4. **The clinician edits real values.** The API returns summaries with placeholders replaced and span offsets translated to the original note; the UI never handles placeholders. Edits are sent in the same schema (cleared fields become "not documented", fields filled from nothing carry no sources or confidence).
5. **Approval is explicit and recoverable until confirmed.** Approve opens a confirmation that states how many fields were edited, saves pending edits first, then approves. Reject requires a reason. Regenerate warns that unsaved edits are lost.
6. **Forms:** React Hook Form with Zod, visible labels, inline errors tied with `aria-describedby`, and a focusable error summary that links to each field.
7. **Server state:** TanStack Query with polling only while a note is queued or processing (1.5 s on the review page, 3 s on the list).
8. **Auth token in `sessionStorage`.** It dies with the tab and is cleared on 401. This trades some XSS exposure for simplicity; the deployed setup should move to an httpOnly cookie behind the same-origin proxy.
9. **Fonts are bundled** (`@fontsource`), so no third-party requests are made from a clinical UI.

## Added dependencies beyond the base stack
`react-router-dom` (routing), `lucide-react` (SVG icons), `@fontsource-variable/*` (self-hosted fonts).
