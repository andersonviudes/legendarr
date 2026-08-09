// Toggles <html data-theme> between "dark" and "light", persisted in localStorage so it
// survives reloads (read back early in base.html's <head> to avoid a flash of the wrong theme).
const STORAGE_KEY = "legendarr-theme";

document.getElementById("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(STORAGE_KEY, next);
});
