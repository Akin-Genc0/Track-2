# Fathom desk — UX audit and plan

- **Commit audited**: `854ec79` (Akin's monochrome sketch redesign). We keep that direction: paper + ink, Architects Daughter display type, offset "pencil" shadows, hatching. Nothing here changes the palette.
- **Method**: Emil Kowalski's skills (`improve-animations` → AUDIT.md categories + PLAN-TEMPLATE, `find-animation-opportunities` gate, `animate` + RECIPES, `animation-performance`, `apple-design` foundations).
- **Audience**: an analyst who works the queue all day, and a judge who sees it for 10 seconds during a 3-minute demo. When they disagree we side with the analyst: daily use argues for less motion, not more.

## 1. Recon

| Item | Finding |
| --- | --- |
| Stack | Vanilla HTML/CSS/JS (`index.html`, `styles.css`, `app.js`), served by `serve.py`. No libraries, no build step. Stays that way. |
| Motion tokens | `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` and `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)` already exist in `:root`. We extend these and add duration tokens; we add no new curves. |
| Where motion lives | CSS transitions on `.btn`, `.chip`, `.queue-item`, `#q`, `.person-switch button`; `@keyframes bootslide`; `#boot` fade. No JS-driven motion. |
| Personality | A crisp working tool with a hand-drawn skin. Motion must be fast and quiet. The sketch look adds plenty of character already. |
| Frequency map | **100+/day**: j/k navigation, filter keys, search typing. **Tens/day**: hover over queue rows, clicking a hit, switching filters. **Occasional**: following an evidence ID, help sheet. **Rare**: boot. |

## 2. Audit (vetted findings)

| # | Severity | Category | Location | Finding | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | HIGH | Purpose / clarity | `app.js` `renderCase` | The decision and its grounds are split across the stamp, the reason paragraph and a 10-row table. You have to read the table to see *why*. | Add a **verdict strip** beside the stamp: three fact tiles (Name, DOB, Countries), each AGREES / CONTRADICTS / UNKNOWN. |
| 2 | HIGH | Clarity | `styles.css` `.row-unknown`, `.status-pill.unknown` | "Unknown" shows a faint `—` and a blank cell. At a glance it reads as "fine", and it is not visually its own state. | Give each state its own glyph, fill and border: agree `=` (light tint), contradict `≠` (solid ink chip, hatched cells), unknown `?` (dotted outline, empty cells, italic "not on file"). They should differ in shape as well as shade, so they still work in greyscale print. |
| 3 | HIGH | Clarity | `app.js` `highlightReason` | Evidence IDs in the reason are inert `<span>`s. The brief's "cited evidence" can't be followed to the source record. | Make every ID token (`CUS-`, `KYC-`, `NOTE-`, `SR-`, `ACC-`, `APP-`, `H-`, `A-`) a `<button>` that scrolls to its evidence card and flashes it. Cards for IDs that the reason mentions but the evidence list omits are added to the grid too. |
| 4 | MEDIUM | Accessibility | `styles.css` reduced-motion block | `transition-duration: 0.01ms !important` on `*` removes all feedback, including opacity changes that help comprehension. | Reduced motion keeps opacity fades and drops movement. Tokens are switched under `@media (prefers-reduced-motion: reduce)`: translate distances go to 0 and durations stay the same. |
| 5 | MEDIUM | Physicality | `.ev-card:hover` | Has a hover `transform` but no `transition`, so it jumps. | `transition: transform 150ms var(--ease-out), box-shadow 150ms var(--ease-out)`. |
| 6 | MEDIUM | Missed feedback | `.help` | The modal appears and disappears instantly. | Modal recipe: `opacity` + `scale(0.97)`, 200ms `--ease-out`, centred origin (modals are exempt from trigger origin). |
| 7 | LOW | Easing | `@keyframes bootslide` | `ease-in-out` on a looping progress bar. | `linear`, which AUDIT §2 prescribes for constant motion. |
| 8 | LOW | Cohesion | Several hand-typed `140ms` / `150ms` durations | Near-duplicates. | Tokens: `--dur-press: 140ms`, `--dur-fast: 180ms`, `--dur-base: 220ms`. |
| 9 | LOW | Wayfinding | Queue rail | Shortcuts are only discoverable through `?`. | A persistent shortcut hint at the foot of the rail. |

Already correct, so not reported: explicit transition property lists (no `transition: all`), hover motion gated by `(hover: hover) and (pointer: fine)`, `tabular-nums` on the stats, press feedback on buttons and chips.

## 3. Animation opportunities (passed the gate)

| # | Location | Today | Purpose | Frequency | Motion |
| --- | --- | --- | --- | --- | --- |
| A | Stage on **pointer** selection | Content swaps instantly | Spatial consistency (list → detail) | Tens/day | `.case` enters from `opacity: 0; translateX(-6px)` (from the rail side) to rest, 200ms `--ease-out`. CSS animation on a freshly mounted node, so a new click restarts on a new node and nothing piles up. |
| B | Comparison rows and verdict tiles | All appear at once | Preventing a jarring change, and directing the eye to the facts | Tens/day (with A only) | Stagger 0 / 30 / 55 / 75 / 90ms (non-uniform, capped at 8 rows; later rows get no delay), `opacity` + `translateY(4px)`, 200ms `--ease-out`. Decorative: never blocks clicks. |
| C | Queue count and chip counts after a filter change | The number changes silently | State indication | Tens/day | WAAPI on the count: `scale(1.12) → 1` and an ink underline `opacity 1 → 0`, 240ms `--ease-out`. It runs only when the number actually changed. |
| D | Evidence card after an ID click | Nothing | Feedback + spatial consistency | Occasional | `scrollIntoView({behavior: smooth})` (instant under reduced motion), then a ring on a `::after` pseudo-element: `opacity 0 → 1 → 0` over 900ms. One beat, so it reads as "here", not a loop. |
| E | Decision stamp | Static | State indication | Tens/day (with A only) | Stamp press: `scale(1.06) rotate(-3deg)` → `scale(1) rotate(-3deg)`, opacity 0 → 1, 220ms `--ease-out`. Reads as a rubber stamp landing and suits the sketch skin. |

## 4. Rejected (deliberately not animated)

- **j / k and arrow-key navigation**: keyboard-initiated, 100+/day. **The detail pane swaps instantly, with no stagger and no stamp press.** We gate A, B and E on pointer input only. This is Emil's rule ("Raycast has no open/close animation"), and it means an analyst holding `j` can move through the queue as fast as they like.
- **Filter keys 1–4 / search typing**: the queue re-renders instantly. Only the count gets C, because it is the one number that tells you the filter worked.
- **Queue row entrance stagger**: the list is scanned all day, so a stagger would only be decoration.
- **Header stats count-up**: these are numbers judges read and quote, so they must never be mid-animation.
- **Hover lift on the comparison table**: this is data the user is reading; it should not move for style.

## 5. Clarity and layout changes (non-motion)

1. **Decision vocabulary**: every hit reads **SAME / DIFFERENT / REVIEW** (the system's labels) with a plain gloss ("true match", "cleared", "needs a human"). The header keeps the analyst's words: Hits · Cleared · Matches · Review · Practice `50/50` · `0` unsafe.
2. **Verdict strip** (finding 1): `[stamp] [Name =] [DOB ≠] [Countries ?]` in one row. A judge gets the decision and its grounds in one look.
3. **Comparison table**: Name, DOB, Nationality and Countries come first, then entity type. Weak fields (address, identifiers, occupation, gender) collapse under "More fields" so the core facts stay above the fold. A legend explains the three states.
4. **Header stats** are computed from the bundle: `counts` from predictions, `correct/labeled` from the practice labels (or `meta.practice_score` as a fallback), and `unsafe` from the cost matrix. No literals.
5. **Keyboard**: `j`/`k` and `↓`/`↑` to move, `1`–`4` for All / Same / Different / Review, `/` to search, `Esc` to clear, `?` for help. A hint bar sits at the bottom of the rail.
6. **Focus states**: 2px ink outline with 2px offset via `:focus-visible` on every control, including ID buttons and queue rows.
7. **Empty states**: if search returns no hits, the rail shows "No hits match 'x'" with a Clear button. The stage keeps the hand-drawn "Select a hit".
8. **Offline**: no new dependencies. Google Fonts stays as a progressive enhancement, and each face has a local fallback stack, so the desk still renders without network.

## 6. Tokens added

```css
--dur-press: 140ms;   /* :active feedback */
--dur-fast: 180ms;    /* hover, small state changes */
--dur-base: 220ms;    /* entrances: case, rows, stamp, modal */
--shift: 6px;         /* entrance travel; 0 under reduced motion */
```

## 7. Verification

- Serve: `python3 ui/serve.py`, open `http://127.0.0.1:8765`.
- Feel check: click several hits in a row and confirm the pane slides in from the rail side and never stacks or stutters. Hold `j` and confirm instant swaps with no motion at all. Change filters and confirm only the count pulses. Click a `NOTE-…` chip and confirm a smooth scroll and one ring flash.
- In DevTools → Rendering, emulate `prefers-reduced-motion: reduce`. Movement should disappear, fades should remain, and the ID scroll should become instant.
- Performance: every animated property is `transform` or `opacity`. No layout properties animate.
- Screenshots are refreshed in `ui/screenshots/`.

## 8. Refinement pass 2: QA at 1280×800 and 1440×900

Additional skills applied: `design-taste-frontend`, `impeccable` (context, craft floor, polish playbook, detector), `emil-design-eng`, `animation-vocabulary`, and the `frontend-app-builder` visual-QA checklist. shadcn/ui served as a reference for control geometry only. No packages were added.

**Committed world kept on purpose.** The craft floor and the taste skill both discourage hard offset shadows, hatching, grid paper and Inter. Each also says that a committed visual world overrides them, and Akin's sketch desk is that world. The hatching carries meaning (it marks "contradicts"). The impeccable detector's remaining flags (`overused-font`, `repeating-stripes-gradient`, and `marquee` on the boot progress bar, which is a load indicator) are therefore deliberate and stay.

| # | Found | Size | Fix |
| --- | --- | --- | --- |
| 1 | The six header stats overflowed and scrolled horizontally | 1280 | Tighter stat padding at ≤1366px; Reload collapses to its icon |
| 2 | The "Date of birth" tile label wrapped, so the three fact tiles had uneven heights | 1280 | Tile label "DOB" (the table keeps "Date of birth"); nowrap labels; tighter state-pill tracking at ≤1366px |
| 3 | The "List entry" key wrapped inside the tiles | 1280 | Key shortened to "List"; the table header still says "List entry" |
| 4 | Long names were truncated with no way to read them | both | `title` on truncated tile values |
| 5 | Unicode glyphs stood in for icons (`= ≠ ? ✓ +`) | both | Lucide-style inline SVG icons (equal, not-equal, help, check, x, chevron, shield-check, alert, search-x, search, refresh, upload, keyboard), one stroke family |
| 6 | Thick `border-left` accents on the practice-label row and on contradicting table rows | both | Replaced with a check / x badge and a bold label; the hatching already carries the state |
| 7 | Functional text below 11px (detector `undersized-ui-text`, 34 declarations) | both | An 11px floor across labels, pills, badges and tabs |
| 8 | Buttons, chips and toggles each had their own height and padding | both | Shared `--control-h: 32px` / `--control-h-sm: 28px`, one focus ring (2px ink, 2px offset) |
| 9 | Evidence cards lifted on hover even though they are data being read | both | Hover lift removed (Emil: functional data does not move for style) |
| 10 | `--text-faint` #6f6f6f measured about 4.3:1 on the rail's #e9e9e9 | both | Changed to #636363 (≥4.5:1) |
| 11 | Browser surfaces were unthemed | both | `caret-color` / `accent-color` set to ink; `tabular-nums` on table cells, tiles, IDs and counts |
| 12 | Em-dashes in visible copy ("—" for missing values, page title) | both | "Not on file" / "n/a"; title "Fathom · Watchlist entity review" |
| 13 | Long evidence values (emails) could overflow card rows | 1440 | `overflow-wrap: anywhere` on evidence values |
| 14 | "More fields" used a text `+` | both | Chevron that rotates 90° on open (180ms, `--ease-out`, transform only) |

Re-verified after fixes: no page or header overflow at either size, no console errors, and the keyboard path (j/k, 1–4, /, Esc, ?), ID-chip jumps, filter count ticks and the empty state all pass in headless Chrome. Screenshots 01–10 were recaptured.

## 9. Merge with Akin's soft monochrome redesign (origin/akin/work, `d2e8751` + `abec640`)

Akin replaced the sketch styling with a soft monochrome dashboard: white cards on #ececea, 16–20px radii, blur shadows, and Inter Tight display type. His visual direction wins. Sections 1–8 still describe the clarity, motion and keyboard work, but anything they say about hatching, offset shadows or the hand-drawn face is now history. This layer was re-applied on his tokens.

| Conflict | Resolution |
| --- | --- |
| `ui/styles.css` (both rewrote it) | Took Akin's file whole as the base. Re-applied the clarity, motion and keyboard layer at the end, rebuilt on his tokens (`--card`, `--card-2/3`, `--line`, `--line-2`, `--ease`, `--r-inner`, `--r-pill`): his soft cards, his pill shapes, no hatching, no offset shadows. |
| Contradicts vs unknown without hatching | Still distinct in shape: **contradicts** is a 1.5px ink outline with a filled ink pill (≠); **unknown** is a dashed outline with no fill (?); **agrees** is his plain hairline card (=). |
| Decision stamp | His flat, unrotated card stamp is kept. My rubber-stamp rotation is dropped, and the entrance became a 0.97 → 1 settle plus fade (220ms, ease-out). |
| Search icon | His field already draws a search icon as a background image, so I removed my inline SVG to avoid a double icon. The `/` hint stays. |
| `ui/app.js` (one sentence) | Kept my rewritten evidence note with his wording: "CITED badge" instead of "CITED tab". |
| `ui/index.html` | Auto-merged: his fonts (Inter Tight), theme colour and favicon, plus my icons, shortcut hint and the em-dash-free title. |
| `ui/screenshots/01–06` (binary) | Kept mine, then recaptured all ten against the merged UI. |
| His reduced-motion block (`0.01ms` on everything) | Replaced with the gentler block: fades kept, travel and scale dropped (AUDIT §6). |
| `--faint` #8d8d88 (3.4:1 on white) | Raised to #6c6c68 (≥4.5:1). An 11px floor was applied to his sub-11px labels (26 declarations), per the impeccable `undersized-ui-text` check. |

Two defects in the incoming stylesheet were fixed without changing his values:
- A stray `}` in the 900px media query made `.case-title { font-size: 28px }` and the narrow `.stat` sizes apply at every width.
- A lost `.fh {` selector left the table-header declarations orphaned inside another 900px block, so the header row rendered as unstyled 16px text. The selector is restored.

QA re-run at 1280×800 and 1440×900 after the merge: no page or header overflow, no console errors, and the keyboard path, ID jumps, count ticks, empty state and help all pass.
