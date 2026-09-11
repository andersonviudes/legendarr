---
name: legendarr-readme-html-sanitizer-gotcha
description: GitHub strips `style` from README HTML, and `align="middle"` is not CSS middle — only `align="absmiddle"` vertically centers an image against text
type: feedback
---

Never style raw HTML in `README.md` with a `style` attribute — GitHub's markdown sanitizer drops
it and substitutes its own, so the declaration is silently ignored. Use the legacy presentational
attributes its allowlist keeps (`align`, `width`, `height`, `alt`). To vertically center an image
against text, the value is **`absmiddle`, not `middle`**.

**Why:** the README header's logo sat visibly above the wordmark because it carried
`style="vertical-align: middle;"`, which GitHub throws away — leaving the image on its
`baseline` default. Swapping in `align="middle"` then pushed it visibly *below* the text, because
browsers map that value to `-webkit-baseline-middle`/`-moz-middle-with-baseline`, which centers
the image on the **baseline itself**, not on the text's optical center. `absmiddle` (and only
`absmiddle`) maps to real `vertical-align: middle`. Measured 2026-09-11 on the live README with
Playwright, as offset of the image's center from the text's center (negative = too high):

| `align` value | computed `vertical-align` | offset |
|---|---|---|
| none / `bottom` / `top` | `baseline` / `top` | -4.0px |
| `texttop` | `text-top` | -2.0px |
| **`absmiddle`** | **`middle`** | **+2.5px** |
| `middle` / `center` | `-webkit-baseline-middle` | +11.0px |

`absmiddle` also holds up if the icon is resized later, since it centers on the x-height midline
rather than pinning an edge the way `texttop` does.

Two more things the same renderer does to the badge row, both found the same day:

- **An `<img>` you don't link, GitHub links for you** — to the image file itself. Dropping the
  `<a>` around the code-size badge didn't make it unlinked, it made it point at the camo-proxied
  shields.io SVG instead of the repo. There is no such thing as an unlinked image in a README, so
  the choice is only ever *which* target, never whether. (The repo link is the useful target here
  anyway: on the Docker Hub overview, which gets this same README, it's the way back to GitHub.)
- **Whitespace inside an `<a>` gets underlined along with it.** GitHub underlines links in
  markdown by default, and an anchor written across three lines
  (`<a>` ⏎ indent ⏎ `<img>` ⏎ `</a>`) holds leading/trailing spaces that render as short blue
  dashes in the gaps between badges. Keep each badge on one line —
  `<a href="..."><img ...></a>` — with the newline *between* anchors, not inside them: the gap
  is identical (4.4px either way) but the spacing text now sits in the `<p>`, where nothing
  underlines it.

**How to apply:** editing the README header, badge row, or any other inline HTML there, reach for
`align="absmiddle"`/`align="center"` rather than CSS, and confirm the sanitizer keeps it with

```
gh api -X POST /markdown -f mode=gfm -f text='<img src="x.png" width="32" height="32" align="absmiddle">'
```

Don't trust a local markdown preview: it doesn't sanitize, so it renders CSS GitHub will discard
and can map legacy `align` values differently. This applies to the Docker Hub Repository Overview
too: the release workflow pushes this same `README.md` as the description (see
[[legendarr-versioning-release-pipeline]]), and that renderer sanitizes as well. Only the
repo-relative logo/`LICENSE`/`docker-compose.example.yml` links get rewritten for Docker Hub, by
a `sed` step in `.github/workflows/release.yml` — nothing rewrites styling.
