// Sitewide toast notifications (loaded directly in base.html, like sidebar.js/theme.js —
// every page can trigger one). Three triggers:
//   - same-page form errors: a page renders a hidden `[data-toast-message]` element (see
//     arr_service_form.html / language_profile_form.html) — shown once on load, then removed.
//   - post-redirect success: a `toast`/`toast_type` query param surviving the redirect —
//     shown once on load, then stripped via history.replaceState so a reload doesn't repeat it.
//   - HTMX swap results: a `[data-toast-message]` element swapped into the DOM by an hx-*
//     request (see _test_result.html) — shown on the next htmx:afterSwap, then removed.
const TOAST_DURATION_MS = 3000;

function showToast(message, type) {
  const container = document.getElementById("toast-container");
  if (!container || !message) return;
  const toast = document.createElement("div");
  toast.className = `toast toast--${type || "success"}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }, TOAST_DURATION_MS);
}
window.showToast = showToast;

function fireToastTriggersIn(root) {
  root.querySelectorAll("[data-toast-message]").forEach((el) => {
    showToast(el.dataset.toastMessage, el.dataset.toastType);
    el.remove();
  });
}

fireToastTriggersIn(document);

// HTMX swaps (e.g. the arr-service "Test" button's result) land in the DOM without a page
// load, so a trigger swapped in that way needs its own scan.
document.addEventListener("htmx:afterSwap", (event) => fireToastTriggersIn(event.detail.target));

const params = new URLSearchParams(window.location.search);
const toastMessage = params.get("toast");
if (toastMessage) {
  showToast(toastMessage, params.get("toast_type"));
  params.delete("toast");
  params.delete("toast_type");
  const query = params.toString();
  const newUrl = window.location.pathname + (query ? `?${query}` : "") + window.location.hash;
  window.history.replaceState({}, "", newUrl);
}
