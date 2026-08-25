// The topbar's running-tasks badge (base.html) polls `every 3s`, but most triggered
// actions (Sync Now, Scan Disk, Translate now, Manual search, timing sync, ...) finish
// well under that — the badge's next scheduled poll can easily land after the job is
// already done and miss it entirely. Nudge it to refresh right after any POST completes
// instead of waiting out the interval.
document.body.addEventListener("htmx:afterRequest", (event) => {
  if (event.detail.requestConfig?.verb !== "post") return;
  const tasksEl = document.querySelector(".app-topbar-tasks");
  if (tasksEl) htmx.trigger(tasksEl, "refresh-tasks");
});
