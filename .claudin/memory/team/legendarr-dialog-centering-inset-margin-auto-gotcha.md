---
name: legendarr-dialog-centering-inset-margin-auto-gotcha
description: Native <dialog> centering via inset:0 + margin:auto doesn't shrink-wrap with height:auto — use top/left:50%+transform instead
type: project
---

Centering a native `<dialog>` box with `inset: 0` (all four sides pinned to 0) paired
with `margin: auto` only shrink-wraps to content when width/height are fixed lengths.
With `height: auto` and both top and bottom pinned to 0, the box stretches to fill the
full viewport height instead of centering around its content — auto margins resolve to
whatever space is left over, not to true centering. This was verified empirically in
`.dir-browser-modal` and `.subtitle-acquire-modal`
(`src/web/src/legendarr_web/static/styles.css`), which showed a large blank gap below a
short popup's content.

Fix: reset `inset: auto` and center with `top: 50%; left: 50%;
transform: translate(-50%, -50%); margin: 0;` instead — this shrink-wraps regardless of
content height. Add `max-height: calc(100vh - 2rem); overflow: auto;` as a safety net so
tall content doesn't overflow the viewport (matches Pico's own `dialog > article`
treatment).

**Why:** Pico's vendored `dialog{}` rule already sets `inset: 0` plus
width/height:inherit/100%, expecting a nested `<article>` for the actual box; this
markup skips that and styles `<dialog>` directly, and an earlier reset toward
inset:0+margin:auto looked like the classic centering trick but doesn't shrink-wrap.
**How to apply:** When adding or debugging any `<dialog>`-based modal in legendarr_web
(or diagnosing a popup with unexplained blank space at the bottom), use the
top/left/transform centering pattern, not inset:0+margin:auto, whenever the dialog's
height should hug its content.
