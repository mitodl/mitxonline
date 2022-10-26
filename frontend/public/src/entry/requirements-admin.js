import { JSONEditor } from "@json-editor/json-editor"

document.addEventListener("DOMContentLoaded", function() {
  // just in case, we iterate on all of the potential editors
  const elements = document.querySelectorAll(".program-requirements-field")

  for (const element of elements) {
    const input = element.querySelector(":scope > input[type=hidden]")
    const script = element.querySelector(`:scope > #${input.name}-schema`)
    const schema = JSON.parse(script.textContent)
    const container = element.querySelector(":scope >.editor-container")
    const value = JSON.parse(input.value)

    const editor = new JSONEditor(container, {
      disable_array_delete_all_rows: true,
      disable_array_delete_last_row: true,
      disable_collapse:              true,
      disable_edit_json:             true,
      disable_properties:            true,
      keep_oneof_values:             false,
      no_additional_properties:      true,
      schema:                        schema,
      startval:                      value,
      use_name_attributes:           false
    })

    editor.on("change", function() {
      input.value = JSON.stringify(editor.getValue())
    })
  }
})
