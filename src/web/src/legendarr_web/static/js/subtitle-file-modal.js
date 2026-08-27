// Wires the per-file subtitles <dialog> (movie/series detail pages): every external and
// embedded pill on a row opens the same dialog, keyed by #subtitle-file-modal-<media_file_id>
// — see subtitle_pill_list() in macros.html. Content is rendered server-side inline rather
// than fetched via htmx (unlike subtitle-acquire.js's dialog), since the pill list already
// has every subtitle in hand when the row is rendered, so there's nothing to fetch. Same
// open/close-on-backdrop shape as subtitle-acquire.js otherwise.
document.addEventListener("click", function (event) {
  var trigger = event.target.closest("[data-subtitle-file-modal-open]");
  if (trigger) {
    var dialog = document.getElementById(trigger.getAttribute("data-subtitle-file-modal-open"));
    if (dialog) dialog.showModal();
    return;
  }

  var closeBtn = event.target.closest("[data-subtitle-file-modal-close]");
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

document.addEventListener("keydown", function (event) {
  if (event.key !== "Enter" && event.key !== " ") return;
  // The trigger is a `<span role="button">`, not a real `<button>`, so it needs its own
  // keydown handling for Enter/Space — same reason subtitle-pill-menu.js has one.
  var trigger = event.target.closest("[data-subtitle-file-modal-open]");
  if (!trigger) return;
  event.preventDefault();
  trigger.click();
});
