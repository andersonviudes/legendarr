---
name: legendarr-pico-search-input-specificity-gotcha
description: Pico's built-in input[type=search] padding/height rules silently override custom .app-search-input styling unless specificity matches
type: project
---

Found 2026-08-26 styling the topbar's global search box (`.app-search-input` in
`static/styles.css`, added alongside [[legendarr-ui-design-system]]). Pico ships two
rules that outrank a bare custom class:

- `input:not([type="checkbox"], [type="radio"], [type="range"], [type="file"])[type="search"]`
  sets `padding-inline-start: calc(var(--pico-form-element-spacing-horizontal) + 1.75rem)`
  (specificity 0,2,1) — reserves room for a native search icon Pico doesn't actually
  render for us.
- `input:not([type="checkbox"], [type="radio"], [type="range"])` sets an explicit
  `height: calc(1rem * var(--pico-line-height) + var(--pico-form-element-spacing-vertical) * 2 + ...)`
  (specificity 0,1,1) using Pico's *own* default font-size/spacing, ignoring whatever
  smaller font-size/padding a custom rule declares.

A plain `.app-search-input { padding: ...; }` (specificity 0,1,0) loses to both, so the
field silently rendered ~56px tall with a huge left inset instead of the declared ~36px
— looked "esquisito"/chunky even though the CSS looked correct on paper. `getComputedStyle`
diffs alone didn't explain it; had to use `page.context().newCDPSession(page)` +
`CSS.getMatchedStylesForNode` to see the actually-winning declarations.

**Why:** any future `input[type="search"]` styled with a single custom class will hit the
exact same silent override — easy to lose an hour re-checking the "obviously correct" CSS
before realizing Pico is winning the cascade.

**How to apply:** for any `[type="search"]` (or other form-element type Pico specially
targets — checkbox/radio/range/file all have their own dedicated rules), scope the
override selector to tie-or-beat Pico's specificity, e.g. `.app-search input.app-search-input`
(class + type + class = 0,2,1), and explicitly set `height: auto` to drop Pico's fixed
formula back to intrinsic sizing from your own padding/line-height. Don't just add
padding/height in a lone class rule and trust a visual screenshot — measure the computed
box (or check matched rules via CDP) before calling a form-element style "done".
