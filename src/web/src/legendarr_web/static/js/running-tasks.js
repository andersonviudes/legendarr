// The topbar's notifications badge and panel body (base.html) poll `every 3s`, but most
// triggered actions (Sync Now, Scan Disk, Translate now, Manual search, timing sync, ...)
// finish well under that — the next scheduled poll can easily land after the job is
// already done and miss it entirely. Nudge them to refresh right after any POST completes
// instead of waiting out the interval.
document.body.addEventListener("htmx:afterRequest", (event) => {
  if (event.detail.requestConfig?.verb !== "post") return;
  document
    .querySelectorAll(".app-notifications-badge, #notifications-panel-body")
    .forEach((el) => htmx.trigger(el, "refresh-tasks"));
});
