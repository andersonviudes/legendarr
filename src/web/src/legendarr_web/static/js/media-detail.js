// Copy-to-clipboard for the title button on a movie/series detail page
// (movie_detail.html / series_detail.html). Delegated on the document, same
// data-copy/data-copy-toast pattern as arr-services.js/authentication-settings.js.
document.addEventListener("click", function (event) {
  var button = event.target.closest("[data-copy]");
  if (!button) return;

  // navigator.clipboard is only defined in a secure context (HTTPS, or localhost) — this
  // app is commonly self-hosted over plain HTTP on a LAN, where it's undefined.
  if (!navigator.clipboard) {
    window.showToast("Clipboard isn't available over HTTP — copy the title manually.", "error");
    return;
  }

  navigator.clipboard
    .writeText(button.dataset.copy)
    .then(function () {
      window.showToast(button.dataset.copyToast || "Copied.", "success");
    })
    .catch(function () {
      window.showToast("Couldn't copy the title.", "error");
    });
});
