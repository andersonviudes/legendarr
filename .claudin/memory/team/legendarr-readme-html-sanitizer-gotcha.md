---
name: legendarr-readme-html-sanitizer-gotcha
description: GitHub strips `style` from README HTML, so inline CSS there is silently dead — use the `align` attribute, which survives the sanitizer
type: feedback
---

Never style raw HTML in `README.md` with a `style` attribute — GitHub's markdown sanitizer
drops it and substitutes its own, so the declaration is silently ignored. Use the legacy
presentational attributes its allowlist keeps instead (`align`, `width`, `height`, `alt`).

**Why:** the README header's logo sat visibly above the wordmark for months because it carried
`style="vertical-align: middle;"`. Confirmed 2026-09-11 by feeding both attributes to GitHub's
own renderer:

```
gh api -X POST /markdown -f mode=gfm -f text='<img src="x.png" width="32" height="32" style="vertical-align: middle;" align="middle">'
```

which returns the `img` with `align="middle"` intact and `style` replaced by GitHub's own
`max-width: 100%; height: auto; max-height: 32px`. Without the declaration the image falls back
to `vertical-align: baseline`, which rests its bottom edge on the text baseline — for a 32px
mark next to a 2em `<h1>` that leaves it ~9px above the cap height.

**How to apply:** editing the README header, badge row, or any other inline HTML there, reach
for `align="middle"`/`align="center"` rather than CSS, and verify with the `gh api /markdown`
call above rather than a local markdown preview — local previews don't sanitize, so they render
CSS that GitHub will throw away. This applies to the Docker Hub Repository Overview too: the
release workflow pushes this same `README.md` as the description (see
[[legendarr-versioning-release-pipeline]]), and that renderer sanitizes as well. Only the
repo-relative logo/`LICENSE`/`docker-compose.example.yml` links get rewritten for Docker Hub,
by a `sed` step in `.github/workflows/release.yml` — nothing rewrites styling.
