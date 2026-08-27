// Toggles the sidebar's collapsible nav groups ("Library", "Settings").
document.querySelectorAll(".app-nav-toggle").forEach((toggle) => {
  const submenu = document.getElementById(toggle.getAttribute("aria-controls"));
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    submenu.hidden = expanded;
  });
});

// Toggles the off-canvas sidebar on narrow viewports (see the "Narrow viewports"
// section of styles.css).
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebar = document.getElementById("app-sidebar");
if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener("click", () => {
    const isOpen = sidebar.classList.toggle("is-open");
    sidebarToggle.setAttribute("aria-expanded", String(isOpen));
  });
}
