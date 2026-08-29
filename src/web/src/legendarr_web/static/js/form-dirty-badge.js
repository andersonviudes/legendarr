// Puts a small badge with the number of changed fields on every form's Save button
// (any `.page-toolbar-btn[type=submit][form=...]`), so the user can tell there's
// something pending to save without scanning every field. Also guards navigation away
// from a dirty form: clicking another in-app link pops the shared "Unsaved Changes"
// <dialog> (base.html), and an actual page unload (reload, close tab, address bar) falls
// back to the browser's own native prompt, since that one can't be styled. Reuses the
// same `.app-nav-badge` pill the sidebar's nav counts use. Shared shell behavior —
// belongs to base.html like sidebar.js/topbar.js, not wired per-page.
document.querySelectorAll('.page-toolbar-btn[type="submit"][form]').forEach(trackFormDirtyState);

var dirtyCounts = new Map();

function trackFormDirtyState(button) {
  var form = button.form;
  var label = button.querySelector("span");
  if (!form || !label) return;

  var row = document.createElement("span");
  row.className = "page-toolbar-btn-label-row";
  button.insertBefore(row, label);
  row.appendChild(label);

  var badge = document.createElement("span");
  badge.className = "app-nav-badge";
  badge.hidden = true;
  row.appendChild(badge);

  function snapshot() {
    var values = new Map();
    new FormData(form).forEach(function (value, name) {
      values.set(name, values.has(name) ? values.get(name) + "\u0000" + value : String(value));
    });
    return values;
  }

  var initial = snapshot();

  function update() {
    var current = snapshot();
    var names = new Set(initial.keys());
    current.forEach(function (_value, name) {
      names.add(name);
    });
    var changed = 0;
    names.forEach(function (name) {
      if ((initial.get(name) || "") !== (current.get(name) || "")) changed++;
    });
    badge.textContent = String(changed);
    badge.hidden = changed === 0;
    if (changed > 0) {
      dirtyCounts.set(form, changed);
    } else {
      dirtyCounts.delete(form);
    }
  }

  form.addEventListener("input", update);
  form.addEventListener("change", update);
  // htmx-submitted forms (e.g. backup-restore-form) don't navigate away on success like a
  // plain POST does, so the snapshot needs an explicit reset once the request lands.
  form.addEventListener("htmx:afterRequest", function (event) {
    if (event.detail.successful) {
      initial = snapshot();
      update();
    }
  });
}

function totalDirtyCount() {
  var total = 0;
  dirtyCounts.forEach(function (count) {
    total += count;
  });
  return total;
}

// A real page unload (reload, close tab, typing a new URL) can't be intercepted with a
// custom dialog — browsers ignore any text set here and show their own fixed prompt —
// but it still needs the guard, since the click handler below only covers in-app links.
// `leaving` is set right before a Save submit or a confirmed "Leave" so that expected
// navigation doesn't *also* trigger this native prompt on top of the one the user just
// answered.
var leaving = false;

document.addEventListener("submit", function () {
  leaving = true;
});

window.addEventListener("beforeunload", function (event) {
  if (leaving || totalDirtyCount() === 0) return;
  event.preventDefault();
  event.returnValue = "";
});

// Custom confirm dialog (base.html's #unsaved-changes-modal) for navigating to another
// in-app link — sidebar, topbar, or any other <a href> — while a form is dirty.
var unsavedDialog = document.getElementById("unsaved-changes-modal");
var pendingHref = null;

document.addEventListener("click", function (event) {
  if (!unsavedDialog) return;

  if (event.target.closest("[data-unsaved-changes-stay], [data-unsaved-changes-close]")) {
    unsavedDialog.close();
    return;
  }

  if (event.target.closest("[data-unsaved-changes-leave]")) {
    var href = pendingHref;
    unsavedDialog.close();
    if (href) {
      leaving = true;
      window.location.href = href;
    }
    return;
  }

  // Native <dialog> backdrop click: the event target is the dialog itself, not a
  // descendant, when the click lands outside the rendered content box.
  if (event.target === unsavedDialog) {
    unsavedDialog.close();
    return;
  }

  if (unsavedDialog.open || totalDirtyCount() === 0) return;

  var link = event.target.closest("a[href]");
  if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

  var rawHref = link.getAttribute("href");
  if (!rawHref || rawHref.charAt(0) === "#" || rawHref.indexOf("javascript:") === 0) return;

  event.preventDefault();
  pendingHref = link.href;

  var total = totalDirtyCount();
  var message = document.getElementById("unsaved-changes-message");
  var template = total === 1 ? message.dataset.messageOne : message.dataset.messageOther;
  message.textContent = template.replace("{count}", String(total));

  unsavedDialog.showModal();
});
