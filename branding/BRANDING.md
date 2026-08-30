# legendarr — icon and palette

Mark: **Caption Stack** — a screen with two subtitle lines and two dots.
Accent: **brass `#d9b98a`** over graphite `#0f1011`.

---

## 1. Files

| File | Use |
|---|---|
| `legendarr-icon.svg` | brass icon, transparent — header, sidebar, 24–48px |
| `legendarr-icon-mono.svg` | uses `currentColor` — inherits color from context (hover, active, disabled) |
| `legendarr-icon-onlight.svg` | graphite version for light backgrounds / README |
| `legendarr-icon-small.svg` | simplified, without the dots — mandatory at ≤ 24px |
| `legendarr-tile.svg` | tile with graphite background and rounded corners |
| `legendarr-mark.svg` `legendarr-mark-512.png` | white-screen mark — same design as the favicon, self-contained on any background — README header |
| `favicon.ico` | 16 + 32 + 48 embedded |
| `favicon-16.png` `favicon-32.png` `favicon-48.png` | individual PNGs |
| `apple-touch-icon-180.png` | iOS / PWA |
| `legendarr-512.png` `legendarr-1024.png` | Docker Hub, Unraid CA, GitHub social preview |

### Installation in `index.html`

```html
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/icon/legendarr-icon.svg">
<link rel="apple-touch-icon" href="/icon/apple-touch-icon-180.png">
<meta name="theme-color" content="#0f1011">
```

### Usage rules

- Clear space around it: at least 12% of the icon's width.
- Never stretch, rotate, tilt, or apply a shadow/gradient.
- Below 24px use `legendarr-icon-small.svg` — the two dots clog up.
- Over a photo or color: use the tile, not the loose icon.
- Wordmark in lowercase: `legendarr`. Never "LegendArr" or "Legendarr" in the product.

---

## 2. Palette — dark theme (default)

### Surfaces (3 steps, back to front)

| Token | Hex | Where |
|---|---|---|
| `--bg` | `#0f1011` | page background |
| `--surface` | `#16171a` | cards, sidebar, header, modals |
| `--surface-hover` | `#1c1e22` | row and card hover |
| `--border` | `#26282c` | borders, dividers, input outline |

### Text

| Token | Hex | Where |
|---|---|---|
| `--text` | `#f0ece6` | titles, large numbers, active menu item |
| `--text-muted` | `#b8b2aa` | body copy, labels |
| `--text-dim` | `#857e75` | metadata, timestamps, hints |

### Accent and states

| Token | Hex | Where |
|---|---|---|
| `--accent` | `#d9b98a` | brand, active-item indicator, primary button, focus |
| `--accent-press` | `#c9a672` | primary button hover/active |
| `--accent-soft` | `rgba(217,185,138,0.12)` | badge background, active-item stripe |
| `--success` | `#7fae8a` | subtitle found, sync ok |
| `--warning` | `#d9b98a` | queued, pending |
| `--danger` | `#c97a6d` | provider failure, error |
| `--info` | `#8aa2b8` | translation in progress |

### Three decisions that make the difference

1. **Gold is scarce.** Only the brand, active state, primary button, and focus ring. Page
   titles ("Dashboard", "Providers", "Live Activity") in `--text`, not gold — today they
   compete with navigation.
2. **Active item = dot + light text**, not gold text. An 8px marker or a 2px stripe in
   `--accent`, with the label in `--text`.
3. **States aren't gold.** If badge, error, and active menu are all amber, nothing stands
   out. Use the desaturated functional colors above.

---

## 3. Palette — light theme

Same brand, same token structure: only the values change. The brass needs to darken on
light (`#d9b98a` over white has too little contrast) — use `--accent` for filled surfaces
and `--accent-ink` when the brass is text or an icon.

### Surfaces

| Token | Hex | Where |
|---|---|---|
| `--bg` | `#faf8f5` | page background — warm white, not pure #fff |
| `--surface` | `#ffffff` | cards, sidebar, header, modals |
| `--surface-hover` | `#f2eee8` | row and card hover |
| `--border` | `#e2dcd3` | borders, dividers, input outline |

### Text

| Token | Hex | Where |
|---|---|---|
| `--text` | `#16171a` | titles, large numbers, active menu item |
| `--text-muted` | `#4f4a44` | body copy, labels |
| `--text-dim` | `#807a72` | metadata, timestamps, hints |

### Accent and states

| Token | Hex | Where |
|---|---|---|
| `--accent` | `#b8873f` | primary button, active indicator, focus ring |
| `--accent-ink` | `#8a6224` | brass as text or icon (AA over white) |
| `--accent-press` | `#9c6f2c` | primary button hover/active |
| `--accent-soft` | `rgba(184,135,63,0.10)` | badge background, active-item stripe |
| `--success` | `#3f7a52` | subtitle found, sync ok |
| `--warning` | `#8a6224` | queued, pending |
| `--danger` | `#a8483a` | provider failure, error |
| `--info` | `#3f6480` | translation in progress |

### Care in light mode

- Shadow instead of a heavy border on cards: `0 1px 2px rgba(22,23,26,0.06)` + `--border`
  border.
- The icon becomes `legendarr-icon-onlight.svg` (graphite) or dark brass `#8a6224` — never
  `#d9b98a` over white.
- No pure white on the page background: `#faf8f5` keeps the warm kinship with the brass.

---

## 4. Prompt to apply to the project

Paste this into a code agent (Claude Code, Cursor, Copilot) at the repository root:

```text
Context: this is legendarr, a web app for downloading and translating subtitles,
integrated with Sonarr and Radarr. Let's standardize the color theme into TWO themes —
dark (default) and light — using the same set of tokens. Today the amber accent
(#e3b27a and variants) is scattered around and also used as a text color, which
makes the interface look flat, and there is no light theme.

Task: refactor the colors into semantic tokens, create both themes, and apply
the rules below. Don't change layout, spacing, typography, components, or
behavior — color only.

1. Find the styling system in use (Tailwind config, CSS variables,
   styled-components, MUI theme) and define the tokens IN IT, using the convention the
   project already uses. Don't introduce a second theming mechanism.

   token          dark (default)           light
   bg             #0f1011                  #faf8f5
   surface        #16171a                  #ffffff
   surface-hover  #1c1e22                  #f2eee8
   border         #26282c                  #e2dcd3
   text           #f0ece6                  #16171a
   text-muted     #b8b2aa                  #4f4a44
   text-dim       #857e75                  #807a72
   accent         #d9b98a                  #b8873f
   accent-ink     #d9b98a                  #8a6224
   accent-press   #c9a672                  #9c6f2c
   accent-soft    rgba(217,185,138,0.12)   rgba(184,135,63,0.10)
   success        #7fae8a                  #3f7a52
   warning        #d9b98a                  #8a6224
   danger         #c97a6d                  #a8483a
   info           #8aa2b8                  #3f6480

   Use accent for filled surfaces (button, indicator) and accent-ink
   when the brass is text or an icon — in light mode the two diverge.

2. Implement the theme switch: dark is the default, light theme under
   [data-theme="light"] on <html> (or whatever mechanism the project already has).
   Respect prefers-color-scheme on the first visit, persist the choice in
   localStorage, and add a discreet toggle in the header. No flash of the
   wrong theme on load.

3. Replace EVERY hardcoded hex, rgb(), or named color in the components with the
   matching token. List at the end any color that didn't map to a token.

4. Apply these rules:
   - Page background = bg. Cards, sidebar, header, and modals = surface with a
     border border (1px). The dashboard cards today nearly disappear into the
     background: make sure there's a contrast step between bg and surface.
   - Section and page titles ("Dashboard", "Providers", "Live Activity") and
     large metric numbers = text. NOT gold.
   - Active navigation item: label in text + indicator in accent (8px dot
     or 2px left bar) + accent-soft background. Inactive item: text-muted;
     hover: text + surface-hover.
   - Primary button: accent background, #14100b text; hover accent-press. Secondary
     button: transparent background, border border, text text.
   - Visible focus ring on every interactive element: 2px accent with a 2px
     offset. Never remove the outline without a replacement.
   - Badges and status use the functional colors (success/danger/info/warning) with
     the same color at 12% opacity for the background and the full color for the text.
     Event-type badges (e.g. acquire_bulk) are neutral: surface-hover background, text-dim
     text.
   - Captions/metadata and timestamps = text-dim.
   - In light mode: cards get a 0 1px 2px rgba(22,23,26,0.06) shadow in addition to
     the border; no pure white on the page background.

5. Icon: use the files under /icon (already in the repository). In the header, swap
   the current icon for legendarr-icon.svg at 32px; below 24px use
   legendarr-icon-small.svg. Register favicon.ico, the SVG, and the
   apple-touch-icon-180.png in index.html, with <meta name="theme-color"
   content="#0f1011">. In light mode use legendarr-icon-onlight.svg (or the mono
   version in #8a6224) — never #d9b98a over white. Wordmark always lowercase:
   legendarr.

6. Check AA contrast IN BOTH THEMES: text over surface, text-muted over
   surface, accent-ink over surface, and accent over bg. Fix anything below
   4.5:1 (3:1 for text ≥ 24px) and tell me what changed.

Deliver a lean diff and a summary of the files touched.
```
