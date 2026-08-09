// Progressive enhancement for the source/target "Languages" fields: turns the plain
// hidden input the macro renders into a tag-style multi-select (chips + a searchable
// dropdown), while the form still only ever submits a single comma-joined string —
// the backend never knows this widget exists.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".lang-multiselect").forEach(initMultiselect);
});

function initMultiselect(root) {
  var tags = root.querySelector(".lang-multiselect-tags");
  var search = root.querySelector(".lang-multiselect-search");
  var options = root.querySelector(".lang-multiselect-options");
  var hiddenInput = root.querySelector('input[type="hidden"]');

  function selectedCodes() {
    return Array.from(tags.querySelectorAll(".lang-multiselect-tag")).map(function (tag) {
      return tag.dataset.code;
    });
  }

  function sync() {
    hiddenInput.value = selectedCodes().join(",");
    // The custom validity message from the submit handler below lives on `search` —
    // hidden inputs are barred from constraint validation, so it can't live on hiddenInput.
    search.setCustomValidity("");
  }

  function openOptions() {
    options.hidden = false;
  }

  function closeOptions() {
    options.hidden = true;
  }

  function filterOptions(query) {
    var needle = query.trim().toLowerCase();
    options.querySelectorAll("li").forEach(function (option) {
      if (option.dataset.selected === "true") {
        option.hidden = true;
        return;
      }
      option.hidden = needle.length > 0 && option.textContent.toLowerCase().indexOf(needle) === -1;
    });
  }

  function selectOption(option) {
    option.dataset.selected = "true";
    option.hidden = true;

    var code = option.dataset.code;
    var tag = document.createElement("li");
    tag.className = "lang-multiselect-tag";
    tag.dataset.code = code;
    tag.innerHTML =
      "<span>" +
      code +
      '</span><button type="button" class="lang-multiselect-tag-remove" aria-label="Remove ' +
      code +
      '">&times;</button>';
    tags.appendChild(tag);

    sync();
    search.value = "";
    filterOptions("");
  }

  function deselectOption(code) {
    var option = options.querySelector('li[data-code="' + code + '"]');
    if (option) option.dataset.selected = "false";
    sync();
  }

  // Mark options that came in pre-selected (server-rendered `hidden` on the <li>)
  // so filterOptions() knows to keep skipping them once the user starts typing.
  options.querySelectorAll("li[hidden]").forEach(function (option) {
    option.dataset.selected = "true";
  });

  root.addEventListener("click", function (event) {
    var removeButton = event.target.closest(".lang-multiselect-tag-remove");
    if (removeButton) {
      var tag = removeButton.closest(".lang-multiselect-tag");
      tag.remove();
      deselectOption(tag.dataset.code);
      return;
    }

    var option = event.target.closest(".lang-multiselect-options li");
    if (option && !option.hidden) {
      selectOption(option);
      return;
    }

    openOptions();
    search.focus();
  });

  search.addEventListener("input", function () {
    openOptions();
    filterOptions(search.value);
  });

  search.addEventListener("keydown", function (event) {
    if (event.key === "Backspace" && search.value === "") {
      var lastTag = tags.querySelector(".lang-multiselect-tag:last-of-type");
      if (lastTag) {
        lastTag.remove();
        deselectOption(lastTag.dataset.code);
      }
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      var firstMatch = options.querySelector("li:not([hidden])");
      if (firstMatch) selectOption(firstMatch);
    }
  });

  document.addEventListener("click", function (event) {
    if (!root.contains(event.target)) closeOptions();
  });
}

// The hidden input can't carry the native `required` attribute (browsers ignore it on
// type="hidden"), so enforce it here — before htmx or a plain submit fires — and surface
// the failure as a normal validation bubble on the visible search input.
document.addEventListener("submit", function (event) {
  var form = event.target;
  var invalid = null;

  form.querySelectorAll(".lang-multiselect[data-required]").forEach(function (root) {
    var hiddenInput = root.querySelector('input[type="hidden"]');
    if (!hiddenInput.value) {
      invalid = root.querySelector(".lang-multiselect-search");
      invalid.setCustomValidity("Select at least one language.");
    }
  });

  if (invalid) {
    event.preventDefault();
    form.reportValidity();
  }
});
