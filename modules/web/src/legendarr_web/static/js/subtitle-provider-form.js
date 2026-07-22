// Client-side guard for the subtitle-provider "Test" button — same pattern as
// arr-service-form.js. The button lives in the page toolbar above the form (not inside
// it, so it can also submit the form via its `form="subtitle-provider-form"` attribute)
// and is a plain type="button", so it bypasses the form's native validation; clear any
// previous result so a stale message doesn't linger while the new probe runs.
document.addEventListener("htmx:beforeRequest", function (event) {
  if (!event.detail.elt.matches("[data-test-connection]")) return;

  var result = document.getElementById("test-result");
  if (result) result.innerHTML = "";
});
