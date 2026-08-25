// Wires the per-subtitle actions menu (movie/series detail pages): clicking a subtitle
// pill opens a small menu of that subtitle's own actions (Sync timing, Translate from
// this, Blacklist), popped open right under it. Same open-on-click/close-on-outside-click
// shape as the language multiselect (language-profile-form.js), just without a
// search/filter step. The trigger is a `<span role="button">`, not a real `<button>`, so
// it needs its own keydown handling for Enter/Space.
document.addEventListener("click", function (event) {
  var trigger = event.target.closest("[data-subtitle-menu-toggle]");
  if (trigger) {
    var menu = trigger.parentElement.querySelector(".subtitle-pill-menu");
    var wasOpen = menu && !menu.hidden;
    closeAllMenus();
    if (menu && !wasOpen) menu.hidden = false;
    return;
  }

  if (!event.target.closest(".subtitle-pill-menu")) closeAllMenus();
});

document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    closeAllMenus();
    return;
  }

  if (event.key !== "Enter" && event.key !== " ") return;
  var trigger = event.target.closest("[data-subtitle-menu-toggle]");
  if (!trigger) return;
  event.preventDefault();
  trigger.click();
});

function closeAllMenus() {
  document.querySelectorAll(".subtitle-pill-menu:not([hidden])").forEach(function (menu) {
    menu.hidden = true;
  });
}
