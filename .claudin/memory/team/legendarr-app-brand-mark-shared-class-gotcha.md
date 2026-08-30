---
name: legendarr-app-brand-mark-shared-class-gotcha
description: .app-brand-mark CSS class is shared by the topbar brand logo AND the login page's lock icon — a blanket edit breaks the other usage
type: project
---

`src/web/src/legendarr_web/static/styles.css`'s `.app-brand-mark` rule (dark tile background +
`color: var(--pico-h1-color)` for a `currentColor` SVG) is applied to two unrelated elements:
the topbar's brand logo (`base.html`, `<span class="app-brand-mark">{{ icon("legendarr-mark") }}</span>`
inside `.app-brand`) and the login page's lock icon (`authentication/templates/login.html`,
`{{ icon("lock") }}` inside a different wrapper, not `.app-brand`). It reads like a
brand-specific class but is actually a generic "icon in a rounded tile" utility.

**Why:** while giving the topbar logo its own white-screen artwork (matching the new
favicon design, see [[legendarr-ui-design-system]]) to replace the dark-tile + brass-glyph
look, editing the shared `.app-brand-mark` rule directly would have also stripped the dark
tile and brass color from the login page's lock icon, which was meant to keep the old look.

**How to apply:** when styling one `.app-brand-mark` usage differently, scope the override
with a more specific selector tied to its actual container (e.g. `.app-brand .app-brand-mark`
for the topbar-only case) instead of editing the base `.app-brand-mark` rule — check every
template that references the class first (`grep -rn 'app-brand-mark' src/web`) before
assuming it's single-purpose.
