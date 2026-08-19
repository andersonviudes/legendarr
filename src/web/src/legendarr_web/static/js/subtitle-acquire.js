// Wires the subtitle-acquire <dialog> (movie/series detail pages): opens/closes it for
// both the "Manual search" and "Upload subtitle" triggers. Delegated on document since the
// dialog's content is swapped in by htmx after the dialog itself already exists in the page.
// Unlike the directory browser, there's no "select and close" step here — a successful
// download/upload just shows a result message in place, and the file row's subtitle badges
// update via an out-of-band swap; the user closes the dialog manually.
document.addEventListener("click", function (event) {
  var trigger = event.target.closest("[data-subtitle-acquire-open]");
  if (trigger) {
    var dialog = document.getElementById("subtitle-acquire-modal");
    if (dialog) dialog.showModal();
    return;
  }

  var closeBtn = event.target.closest("[data-subtitle-acquire-close]");
  if (closeBtn) {
    var closeDialog = closeBtn.closest("dialog");
    if (closeDialog) closeDialog.close();
    return;
  }

  // Native <dialog> backdrop click: the event target is the dialog itself, not a
  // descendant, when the click lands outside the rendered content box.
  if (event.target.tagName === "DIALOG") {
    event.target.close();
  }
});
