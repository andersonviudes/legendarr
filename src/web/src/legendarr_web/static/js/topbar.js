// Topbar disclosures: the notifications bell's dropdown and the global search results,
// both open-on-interaction/close-on-outside-click/Escape, same shape as
// subtitle-pill-menu.js.
var notificationsToggle = document.getElementById("notifications-toggle");
var notificationsPanel = document.getElementById("notifications-panel");
if (notificationsToggle && notificationsPanel) {
  notificationsToggle.addEventListener("click", function () {
    var isOpen = !notificationsPanel.hidden;
    notificationsPanel.hidden = isOpen;
    notificationsToggle.setAttribute("aria-expanded", String(!isOpen));
  });
}

var searchInput = document.getElementById("global-search-input");
var searchResults = document.getElementById("global-search-results");
if (searchInput && searchResults) {
  searchInput.addEventListener("input", function () {
    searchResults.hidden = searchInput.value.trim() === "";
  });
}

document.addEventListener("click", function (event) {
  if (notificationsPanel && !notificationsPanel.hidden && !event.target.closest(".app-notifications")) {
    notificationsPanel.hidden = true;
    notificationsToggle.setAttribute("aria-expanded", "false");
  }
  if (searchResults && !searchResults.hidden && !event.target.closest(".app-search")) {
    searchResults.hidden = true;
  }
});

document.addEventListener("keydown", function (event) {
  if (event.key !== "Escape") return;
  if (notificationsPanel) {
    notificationsPanel.hidden = true;
    notificationsToggle.setAttribute("aria-expanded", "false");
  }
  if (searchResults) searchResults.hidden = true;
});
