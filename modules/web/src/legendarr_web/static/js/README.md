# static/js


JS is kept out of the HTML templates. Convention: one file per page,
named after the template it belongs to (e.g. `dashboard.js` for
`dashboard/templates/dashboard.html`), served from `/static/js/<page>.js`.

A page that needs JS loads it by overriding the `scripts` block from
`shared_kernel/templates/base.html`:

```jinja
{% block scripts %}
<script src="/static/js/dashboard.js" defer></script>
{% endblock %}
```

Exception: `sidebar.js` and `theme.js` belong to the shared sidebar in `base.html` itself
(every page has one), so they're loaded directly in `base.html` rather than through the
per-page `scripts` block.
