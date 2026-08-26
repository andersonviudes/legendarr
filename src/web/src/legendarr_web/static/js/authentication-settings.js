// Settings → Authentication page: reveal/copy for the generated API key
// (settings/templates/_api_key_field.html). Delegated on the document — the field is
// swapped wholesale (outerHTML) after "Regenerate", so a listener bound to the original
// element would be gone after that swap.
document.addEventListener("click", function (event) {
  var toggle = event.target.closest("[data-api-key-toggle]");
  if (toggle) {
    var input = document.querySelector("[data-api-key-input]");
    var showIcon = toggle.querySelector("[data-api-key-icon-show]");
    var hideIcon = toggle.querySelector("[data-api-key-icon-hide]");
    var revealed = input.type === "text";
    input.type = revealed ? "password" : "text";
    showIcon.hidden = !revealed;
    hideIcon.hidden = revealed;
    toggle.setAttribute("aria-label", revealed ? "Show API key" : "Hide API key");
    return;
  }

  var copyButton = event.target.closest("[data-copy]");
  if (!copyButton) return;

  // navigator.clipboard is only defined in a secure context (HTTPS, or localhost) — this
  // app is commonly self-hosted over plain HTTP on a LAN, where it's undefined.
  if (!navigator.clipboard) {
    window.showToast("Clipboard isn't available over HTTP — copy the key manually.", "error");
    return;
  }

  navigator.clipboard
    .writeText(copyButton.dataset.copy)
    .then(function () {
      window.showToast(copyButton.dataset.copyToast || "Copied.", "success");
    })
    .catch(function () {
      window.showToast("Couldn't copy the API key.", "error");
    });
});
