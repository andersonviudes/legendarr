// Client-side guard for the subtitle-proxy "Test" button. The button lives in the page
// toolbar above the form (not inside it, so it can also submit the form via its
// `form="subtitle-proxy-form"` attribute) and is a plain type="button", so it bypasses
// the form's native validation; run reportValidity() before htmx fires the request
// and stop it if the form is incomplete (an empty required field would otherwise POST
// and come back as a confusing error). Also clears any previous result so a stale
// message doesn't linger while the new probe runs.
document.addEventListener("htmx:beforeRequest", function (event) {
  if (!event.detail.elt.matches("[data-test-connection]")) return;

  var form = document.getElementById("subtitle-proxy-form");
  if (form && !form.reportValidity()) {
    event.preventDefault();
    return;
  }

  var result = document.getElementById("test-result");
  if (result) result.innerHTML = "";
});
