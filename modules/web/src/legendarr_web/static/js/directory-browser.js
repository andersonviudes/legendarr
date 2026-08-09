// Wires the directory-browser <dialog> (currently only on arr_service_form.html): opens/
// closes it and, on "Select this directory", writes the chosen path into the field the
// "Browse" button was opened for. Delegated on document since the dialog's content is
// swapped in by htmx after the dialog itself already exists in the page.
document.addEventListener("click", function (event) {
  var trigger = event.target.closest("[data-dir-browser-open]");
  if (trigger) {
    var dialog = document.getElementById("dir-browser-modal");
    if (dialog) dialog.showModal();
    return;
  }

  var closeBtn = event.target.closest("[data-dir-browser-close]");
  if (closeBtn) {
    var closeDialog = closeBtn.closest("dialog");
    if (closeDialog) closeDialog.close();
    return;
  }

  var select = event.target.closest(".dir-browser-select");
  if (select) {
    var input = document.getElementById(select.dataset.target);
    if (input) {
      input.value = select.dataset.path;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    var selectDialog = select.closest("dialog");
    if (selectDialog) selectDialog.close();
    return;
  }

  // Native <dialog> backdrop click: the event target is the dialog itself, not a
  // descendant, when the click lands outside the rendered content box.
  if (event.target.tagName === "DIALOG") {
    event.target.close();
  }
});
