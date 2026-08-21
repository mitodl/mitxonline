import "../../scss/requirements.scss"

/**
 * Renders the Program admin's "Requirements" field as a stack of plain-language
 * requirement groups instead of a generic nested tree-editor form.
 *
 * The field's hidden input carries the same JSON tree
 * `ProgramRequirementTreeSerializer` already expects: a list of top-level
 * operator nodes ("groups"), each with `children` that are either course/program
 * leaves or (rarely) another nested operator node. This file only changes how
 * that JSON is edited, not its shape, so no serializer/backend changes are
 * needed here.
 */

document.addEventListener("DOMContentLoaded", function() {
  document
    .querySelectorAll(".program-requirements-field")
    .forEach(initRequirementsField)
})

function initRequirementsField(root) {
  const input = root.querySelector(":scope > input[type=hidden]")
  const catalogScript = root.querySelector(`:scope > #${input.name}-catalog`)
  const catalog = JSON.parse(catalogScript.textContent)
  const container = root.querySelector(":scope > .editor-container")

  const NODE = catalog.nodeTypes
  const OP = catalog.operatorValues

  // ProgramRequirement.title defaults to "" (not null) at the model level,
  // so existing course/program leaves loaded from the database can carry a
  // blank string here. The API serializer's title field rejects blank
  // strings (only null is allowed), so re-saving an untouched leaf as-is
  // would fail validation - normalize on load instead of carrying it through.
  function normalizeTree(nodes) {
    for (const node of nodes) {
      if (node.data.title === "") node.data.title = null
      normalizeTree(node.children)
    }
  }

  const state = JSON.parse(input.value) || []
  normalizeTree(state)

  function writeInput() {
    input.value = JSON.stringify(state)
  }

  function nodeAt(path) {
    let node = null
    let list = state
    for (const index of path) {
      node = list[index]
      list = node.children
    }
    return node
  }

  function locate(path) {
    if (path.length === 1) {
      return { list: state, index: path[0] }
    }
    const parent = nodeAt(path.slice(0, -1))
    return { list: parent.children, index: path[path.length - 1] }
  }

  function catalogItem(nodeType, id) {
    const list = nodeType === NODE.course ? catalog.courses : catalog.programs
    return list.find(item => item.id === id)
  }

  function leafLabel(node) {
    if (node.data.node_type === NODE.course) {
      const course = catalogItem(NODE.course, node.data.course)
      return course ?
        `${course.code} — ${course.title}` :
        `Course #${node.data.course}`
    }
    const program = catalogItem(NODE.program, node.data.required_program)
    return program ?
      `${program.code} — ${program.title}` :
      `Program #${node.data.required_program}`
  }

  function makeGroup(mode) {
    const isElective = mode === OP.minNumberOf
    return {
      id:   null,
      data: {
        node_type:      NODE.operator,
        title:          isElective ? "New elective group" : "New required group",
        operator:       mode,
        operator_value: isElective ? 1 : null,
        elective_flag:  isElective
      },
      children: []
    }
  }

  function makeLeaf(entry) {
    if (entry.kind === "course") {
      return {
        id:       null,
        data:     { node_type: NODE.course, course: entry.id },
        children: []
      }
    }
    return {
      id:       null,
      data:     { node_type: NODE.program, required_program: entry.id },
      children: []
    }
  }

  function describeGroup(node) {
    const count = node.children.length
    const label = node.data.title || "Untitled group"
    if (node.data.operator === OP.minNumberOf) {
      const n = node.data.operator_value ?? "?"
      return `choose ${n} of ${count} in “${label}”`
    }
    return `complete all ${count} in “${label}”`
  }

  function renderSummary(el) {
    if (!state.length) {
      el.textContent = "No requirements defined yet."
      return
    }
    const parts = state.map(describeGroup)
    const joined =
      parts.length > 1 ?
        `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}` :
        parts[0]
    el.textContent = `To complete this program, students must ${joined}.`
  }

  function render() {
    container.innerHTML = ""

    const summary = document.createElement("div")
    summary.className = "req-summary"
    const summaryIcon = document.createElement("span")
    summaryIcon.className = "req-summary__icon"
    summaryIcon.textContent = "✅"
    const summaryText = document.createElement("p")
    renderSummary(summaryText)
    summary.append(summaryIcon, summaryText)
    container.appendChild(summary)

    const list = document.createElement("div")
    list.className = "req-groups"
    state.forEach((group, index) =>
      list.appendChild(renderGroup(group, [index], 0))
    )
    container.appendChild(list)

    container.appendChild(renderAddGroupRow([]))
  }

  function persistAndRender() {
    writeInput()
    render()
  }

  function renderAddGroupRow(path) {
    const row = document.createElement("div")
    row.className = "req-add-row"

    const addAllOf = document.createElement("button")
    addAllOf.type = "button"
    addAllOf.className = "req-add-btn"
    addAllOf.textContent =
      path.length === 0 ?
        "+ Add a required group (all of)" :
        "+ Add a required sub-group"
    addAllOf.addEventListener("click", () => {
      const list = path.length === 0 ? state : nodeAt(path).children
      list.push(makeGroup(OP.allOf))
      persistAndRender()
    })

    const addChooseN = document.createElement("button")
    addChooseN.type = "button"
    addChooseN.className = "req-add-btn req-add-btn--elective"
    addChooseN.textContent =
      path.length === 0 ?
        "+ Add an elective group (choose N of)" :
        "+ Add an elective sub-group"
    addChooseN.addEventListener("click", () => {
      const list = path.length === 0 ? state : nodeAt(path).children
      list.push(makeGroup(OP.minNumberOf))
      persistAndRender()
    })

    row.append(addAllOf, addChooseN)
    return row
  }

  function renderGroup(node, path, depth) {
    const el = document.createElement("div")
    el.className = `req-group${depth > 0 ? " req-group--nested" : ""}`
    el.dataset.mode = node.data.operator === OP.minNumberOf ? "choose" : "all"

    el.appendChild(renderGroupHead(node, path))
    el.appendChild(renderGroupSentence(node, path))
    el.appendChild(renderLeafPicker(node))

    const subgroups = node.children.filter(
      child => child.data.node_type === NODE.operator
    )

    if (subgroups.length || depth === 0) {
      const nested = document.createElement("div")
      nested.className = "req-subgroups"
      subgroups.forEach(sub => {
        const subIndex = node.children.indexOf(sub)
        nested.appendChild(renderGroup(sub, [...path, subIndex], depth + 1))
      })
      const addNested = document.createElement("button")
      addNested.type = "button"
      addNested.className = "req-add-nested-btn"
      addNested.textContent = "+ Add nested elective sub-group"
      addNested.addEventListener("click", () => {
        node.children.push(makeGroup(OP.minNumberOf))
        persistAndRender()
      })
      nested.appendChild(addNested)
      el.appendChild(nested)
    }

    return el
  }

  function renderGroupHead(node, path) {
    const head = document.createElement("div")
    head.className = "req-group__head"

    const handle = document.createElement("span")
    handle.className = "req-group__handle"
    handle.textContent = "⠿"
    handle.title = "Groups are ordered top to bottom"

    const title = document.createElement("input")
    title.type = "text"
    title.className = "req-group__title"
    title.value = node.data.title || ""
    title.placeholder = "Group title"
    title.addEventListener("input", event => {
      node.data.title = event.target.value
      writeInput()
      const summaryText = container.querySelector(".req-summary p")
      if (summaryText) renderSummary(summaryText)
    })

    const pill = document.createElement("span")
    const isElective = node.data.operator === OP.minNumberOf
    pill.className = `req-group__pill ${
      isElective ? "req-group__pill--choose" : "req-group__pill--all"
    }`
    pill.textContent = isElective ? "ELECTIVE" : "ALL REQUIRED"

    const remove = document.createElement("button")
    remove.type = "button"
    remove.className = "req-group__remove"
    remove.textContent = "✕"
    remove.title = "Remove group"
    remove.addEventListener("click", () => {
      const { list, index } = locate(path)
      list.splice(index, 1)
      persistAndRender()
    })

    head.append(handle, title, pill, remove)
    return head
  }

  function renderGroupSentence(node) {
    const sentence = document.createElement("div")
    sentence.className = "req-group__sentence"

    const lead = document.createElement("b")
    lead.textContent = "Students must complete"

    const segmented = document.createElement("div")
    segmented.className = "req-segmented"

    const allBtn = document.createElement("button")
    allBtn.type = "button"
    allBtn.textContent = "All of these"
    allBtn.className = node.data.operator === OP.allOf ? "active" : ""

    const chooseBtn = document.createElement("button")
    chooseBtn.type = "button"
    chooseBtn.textContent = "Choose these"
    chooseBtn.className = node.data.operator === OP.minNumberOf ? "active" : ""

    function setMode(mode) {
      node.data.operator = mode
      if (mode === OP.minNumberOf) {
        node.data.elective_flag = true
        if (!node.data.operator_value) node.data.operator_value = 1
      } else {
        node.data.elective_flag = false
        node.data.operator_value = null
      }
      persistAndRender()
    }
    allBtn.addEventListener("click", () => setMode(OP.allOf))
    chooseBtn.addEventListener("click", () => setMode(OP.minNumberOf))

    segmented.append(allBtn, chooseBtn)
    sentence.append(lead, segmented)

    if (node.data.operator === OP.minNumberOf) {
      const stepper = document.createElement("div")
      stepper.className = "req-stepper"
      const dec = document.createElement("button")
      dec.type = "button"
      dec.textContent = "–"
      const n = document.createElement("span")
      n.className = "req-stepper__n"
      n.textContent = String(node.data.operator_value ?? 1)
      const inc = document.createElement("button")
      inc.type = "button"
      inc.textContent = "+"

      const maxValue = Math.max(1, node.children.length)
      dec.addEventListener("click", () => {
        node.data.operator_value = Math.max(
          1,
          (node.data.operator_value || 1) - 1
        )
        persistAndRender()
      })
      inc.addEventListener("click", () => {
        node.data.operator_value = Math.min(
          maxValue,
          (node.data.operator_value || 1) + 1
        )
        persistAndRender()
      })

      stepper.append(dec, n, inc)
      sentence.appendChild(stepper)
    }

    const of = document.createElement("span")
    of.textContent = "of these"
    sentence.appendChild(of)

    return sentence
  }

  function renderLeafPicker(node) {
    const picker = document.createElement("div")
    picker.className = "req-picker"

    const chips = document.createElement("div")
    chips.className = "req-chips"
    node.children
      .filter(child => child.data.node_type !== NODE.operator)
      .forEach(leaf => {
        const chip = document.createElement("span")
        chip.className = "req-chip"
        if (leaf.data.node_type === NODE.program) {
          const badge = document.createElement("span")
          badge.className = "req-chip__badge"
          badge.textContent = "PROGRAM"
          chip.appendChild(badge)
        }
        const label = document.createElement("span")
        label.textContent = leafLabel(leaf)
        chip.appendChild(label)

        const remove = document.createElement("button")
        remove.type = "button"
        remove.textContent = "✕"
        remove.title = "Remove"
        remove.addEventListener("click", () => {
          const idx = node.children.indexOf(leaf)
          node.children.splice(idx, 1)
          persistAndRender()
        })
        chip.appendChild(remove)
        chips.appendChild(chip)
      })
    picker.appendChild(chips)

    picker.appendChild(renderCombobox(node))
    return picker
  }

  function renderCombobox(node) {
    const combo = document.createElement("div")
    combo.className = "req-combobox"

    const box = document.createElement("input")
    box.type = "text"
    box.placeholder = "Search courses and programs to add…"
    const list = document.createElement("div")
    list.className = "req-combobox__list"
    combo.append(box, list)

    function selectedIds(kind) {
      return node.children
        .filter(child => child.data.node_type === kind)
        .map(child =>
          kind === NODE.course ? child.data.course : child.data.required_program
        )
    }

    function allEntries() {
      const usedCourses = new Set(selectedIds(NODE.course))
      const usedPrograms = new Set(selectedIds(NODE.program))
      const courseEntries = catalog.courses
        .filter(c => !usedCourses.has(c.id))
        .map(c => ({ kind: "course", id: c.id, code: c.code, title: c.title }))
      const programEntries = catalog.programs
        .filter(p => !usedPrograms.has(p.id))
        .map(p => ({ kind: "program", id: p.id, code: p.code, title: p.title }))
      return [...courseEntries, ...programEntries]
    }

    function updateList(query) {
      const q = (query || "").toLowerCase()
      const matches = allEntries().filter(
        entry =>
          entry.code.toLowerCase().includes(q) ||
          entry.title.toLowerCase().includes(q)
      )
      list.innerHTML = ""
      if (!matches.length) {
        const empty = document.createElement("div")
        empty.className = "req-combobox__empty"
        empty.textContent = "No matching courses or programs"
        list.appendChild(empty)
        return
      }
      matches.slice(0, 50).forEach(entry => {
        const opt = document.createElement("div")
        opt.className = "req-combobox__opt"
        if (entry.kind === "program") {
          const badge = document.createElement("span")
          badge.className = "req-chip__badge"
          badge.textContent = "PROGRAM"
          opt.appendChild(badge)
        }
        const code = document.createElement("span")
        code.className = "req-combobox__code"
        code.textContent = entry.code
        const title = document.createElement("span")
        title.textContent = entry.title
        opt.append(code, title)
        opt.addEventListener("mousedown", event => {
          event.preventDefault()
          node.children.push(makeLeaf(entry))
          persistAndRender()
        })
        list.appendChild(opt)
      })
    }

    box.addEventListener("focus", () => {
      updateList(box.value)
      list.classList.add("open")
    })
    box.addEventListener("input", () => updateList(box.value))
    box.addEventListener("blur", () =>
      setTimeout(() => list.classList.remove("open"), 150)
    )

    return combo
  }

  render()
}
