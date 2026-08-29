# static/js


JS is kept out of the HTML templates. Convention: one file per page,
named after the template it belongs to (e.g. `dashboard.js` for
`dashboard/templates/dashboard.html`), served from `/static/js/<page>.js`.

A page that needs JS loads it by overriding the `scripts` block from
`templates/base.html`:

```jinja
{% block scripts %}
<script src="/static/js/dashboard.js" defer></script>
{% endblock %}
```

Exception: `sidebar.js`, `theme.js`, `toast.js`, `running-tasks.js`, `topbar.js`, and
`form-dirty-badge.js` belong to `base.html` itself (every page has the sidebar, the theme
toggle, the toast container, the topbar's notifications/search disclosures, the running-tasks
refresh nudge, and — on pages with a form — a Save button that should flag unsaved changes
and, if the user tries to navigate away while dirty, the shared `#unsaved-changes-modal`
confirm dialog), so they're loaded directly in `base.html` rather than through the per-page
`scripts` block.

Exception: `provider-test-connection.js` is shared by any edit-form page whose "Test" button
has no client-side required fields to validate first (`subtitle_provider_form.html`,
`translation_provider_form.html`) — the behavior is identical across those pages, so it isn't
duplicated per-page like `arr-service-form.js`/`subtitle-proxy-form.js` (which additionally run
`reportValidity()` and so stay separate, one per page).

Exception: `directory-browser.js` wires the shared directory-picker `<dialog>` — currently
opened only from `arr_service_form.html`, but the widget isn't tied to that page, so any form
that needs a filesystem-path picker can reuse the same dialog markup and script. It's named
after the widget rather than a page for that reason.

Exception: `subtitle-file-modal.js` wires the per-file subtitles `<dialog>`
(`subtitle_pill_list()` in `macros.html`, loaded from `movie_detail.html` and
`series_detail.html`) — same shared-widget reasoning as `directory-browser.js`.
