// Client-side guard for a provider/proxy "Test" button — shared by every edit form whose
// "Test" button has no client-side required fields to validate first (subtitle-provider-form
// and translation-provider-form; arr-service-form and subtitle-proxy-form additionally run
// reportValidity() first, so they stay separate). The button lives in the page toolbar above
// the form (not inside it, so it can also submit the form via its `form="..."` attribute) and
// is a plain type="button", so it bypasses the form's native validation; clear any previous
// result so a stale message doesn't linger while the new probe runs.
document.addEventListener("htmx:beforeRequest", function (event) {
  if (!event.detail.elt.matches("[data-test-connection]")) return;

  var result = document.getElementById("test-result");
  if (result) result.innerHTML = "";
});
