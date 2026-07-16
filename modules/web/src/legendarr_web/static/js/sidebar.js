// Toggles the sidebar's collapsible nav groups (currently just "Library").
document.querySelectorAll(".app-nav-toggle").forEach((toggle) => {
  const submenu = document.getElementById(toggle.getAttribute("aria-controls"));
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    submenu.hidden = expanded;
  });
});
