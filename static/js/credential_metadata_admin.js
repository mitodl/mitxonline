// "Generate with AI" buttons on CertificatePage's verifiable credential fields.
// Rendered by GenerateWithAIFieldPanel (cms/models.py). Fills a field from MIT
// Learn's stored draft; it never saves the page.
;(function () {
  "use strict"

  var EMPTY_MESSAGE =
    "MIT Learn has no draft for this course yet. You can write your own."
  var UNAVAILABLE_MESSAGE =
    "Couldn't reach MIT Learn. Try again in a moment, or you can still write your own."

  function showMessage(container, text, isError) {
    var message = container.querySelector("[data-credential-metadata-message]")
    message.textContent = text
    message.classList.toggle("error-message", Boolean(isError))
    message.hidden = !text
  }

  function generate(container, button) {
    var target = document.getElementById(button.dataset.credentialMetadataTarget)
    var field = button.dataset.credentialMetadataField
    var note = container.querySelector("[data-credential-metadata-note]")
    var label = button.textContent

    if (
      target.value.trim() &&
      !window.confirm("Replace the text in this field with MIT Learn's draft?")
    ) {
      return
    }

    showMessage(container, "")
    button.disabled = true
    button.setAttribute("aria-busy", "true")
    button.textContent = "Generating…"

    fetch(button.dataset.credentialMetadataUrl, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (response) {
        return response.json()
      })
      .then(function (data) {
        if (data.status === "empty") {
          showMessage(container, EMPTY_MESSAGE)
        } else if (data.status === "ok" && data[field]) {
          target.value = data[field]
          // Let Wagtail notice the edit (unsaved-changes warning, etc.).
          target.dispatchEvent(new Event("input", { bubbles: true }))
          target.dispatchEvent(new Event("change", { bubbles: true }))
          note.hidden = false
        } else if (data.status === "ok") {
          var reason = (data.errors && data.errors[field]) || ""
          showMessage(
            container,
            "MIT Learn couldn't generate this field. " + reason,
            true
          )
        } else {
          showMessage(container, UNAVAILABLE_MESSAGE, true)
        }
      })
      .catch(function () {
        showMessage(container, UNAVAILABLE_MESSAGE, true)
      })
      .finally(function () {
        button.disabled = false
        button.removeAttribute("aria-busy")
        button.textContent = label
      })
  }

  function init() {
    var containers = document.querySelectorAll("[data-credential-metadata]")
    if (!containers.length) {
      return
    }
    var checkbox = document.getElementById(
      "id_should_provision_verifiable_credential"
    )

    function toggle() {
      containers.forEach(function (container) {
        container.hidden = !(checkbox && checkbox.checked)
      })
    }

    containers.forEach(function (container) {
      var button = container.querySelector("[data-credential-metadata-url]")
      button.addEventListener("click", function () {
        generate(container, button)
      })
    })
    if (checkbox) {
      checkbox.addEventListener("change", toggle)
    }
    toggle()
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init)
  } else {
    init()
  }
})()
