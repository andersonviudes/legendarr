// Copy-to-clipboard for the per-connection webhook URL shown on each Arr Services card
// (arr_services.html / macros.html's service_card). Delegated on the document since cards
// are rendered server-side, not swapped in by htmx.
document.addEventListener("click", function (event) {
  var button = event.target.closest("[data-copy]");
  if (!button) return;

  // navigator.clipboard is only defined in a secure context (HTTPS, or localhost) — this
  // app is commonly self-hosted over plain HTTP on a LAN, where it's undefined.
  if (!navigator.clipboard) {
    window.showToast("Clipboard isn't available over HTTP — copy the URL manually.", "error");
    return;
  }

  navigator.clipboard
    .writeText(button.dataset.copy)
    .then(function () {
      window.showToast("Webhook URL copied.", "success");
    })
    .catch(function () {
      window.showToast("Couldn't copy the webhook URL.", "error");
    });
});
