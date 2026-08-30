---
name: legendarr-brand-asset-propagation-check
description: When swapping legendarr's brand mark/icon design, grep all raster/SVG embeds (README.md, BRANDING.md, docs) too — not just the CSS-driven in-app usages
type: feedback
---

When updating the legendarr brand mark's visual design (e.g. the dark-tile + brass-glyph look →
the white-screen look), check every place the old artwork is embedded, not just the CSS class(es)
that render it in the web UI. The topbar's `.app-brand-mark` was fixed first (see
[[legendarr-app-brand-mark-shared-class-gotcha]]), but the README's header `<img>` pointed
straight at the static `branding/legendarr-512.png` — no shared CSS class involved — so it kept
showing the old design. The user had to point this out separately ("esta a mesma coisa no
readme") after the topbar fix had already been declared done and pushed.

**Why:** brand assets in this repo are referenced two different ways — a shared CSS class / SVG
`{{ icon(...) }}` macro for in-app usages, and direct static-file embeds (`<img src=...>`) for
README/docs/social-preview — so a fix scoped to the CSS class doesn't reach the latter.

**How to apply:** after changing a brand asset's design, `grep -rn` the old filename (or another
distinguishing marker of the old design) across `README.md`, `docs/`, and `branding/BRANDING.md`
before calling the change done, not just the templates/CSS that were the original target.
