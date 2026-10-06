import "../../scss/requirements.scss"

/**
 * Renders the Program admin's "Requirements" field as a stack of plain-language
 * requirement groups instead of a generic nested tree-editor form.
 *
 * The field's hidden input carries the JSON tree
 * `ProgramRequirementTreeSerializer` expects: a list of top-level operator
 * nodes ("groups") whose `children` are course/program leaves, or, for one
 * "Minimum # of" group, tracks. A track holds groups of leaves of its own.
 * `validate_requirement_tree` in courses/requirement_tree.py decides what
 * saves. This editor steers toward those shapes: it offers tracks only where
 * they may go, keeps a "Minimum # of" value within the group's item count,
 * and shows anything else it finds in a loaded tree as a chip that can be
 * removed. The validator's errors cover the rest on save.
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
  // so existing nodes loaded from the database can carry a blank string
  // here. The API serializer's title field rejects blank strings (only null
  // is allowed), so re-saving an untouched node as-is would fail validation -
  // normalize on load instead of carrying it through.
  function normalizeTree(nodes) {
    for (const node of nodes) {
      if (node.data.title === "") node.data.title = null
      // operator_value is a CharField, so a saved tree carries "1", and
      // "1" + 1 is "11".
      if (typeof node.data.operator_value === "string") {
        node.data.operator_value = Number(node.data.operator_value)
      }
      normalizeTree(node.children)
    }
  }

  // A "Minimum # of" value above the item count can never be met; the
  // validator rejects it, so keep it in range as items come and go.
  function clampValues(nodes) {
    for (const node of nodes) {
      if (node.data.operator === OP.minNumberOf) {
        const max = Math.max(1, node.children.length)
        node.data.operator_value = Math.min(node.data.operator_value ?? 1, max)
      }
      clampValues(node.children)
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

  function isTrack(node) {
    return node.data.node_type === NODE.track
  }

  function isGroup(node) {
    return node.data.node_type === NODE.operator
  }

  function holdsTracks(group) {
    return group.children.some(isTrack)
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
    if (node.data.node_type === NODE.program) {
      const program = catalogItem(NODE.program, node.data.required_program)
      return program ?
        `${program.code} — ${program.title}` :
        `Program #${node.data.required_program}`
    }
    return node.data.title || "Untitled group"
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

  // A track saves only once one of its groups holds a course or program, so
  // it starts with an empty required group to fill in.
  function makeTrack() {
    return {
      id:       null,
      data:     { node_type: NODE.track, title: "New track", description: "" },
      children: [makeGroup(OP.allOf)]
    }
  }

  function describeGroup(node) {
    const count = node.children.length
    const label = node.data.title || "Untitled group"
    if (holdsTracks(node)) {
      return `complete one of ${count} tracks in “${label}”`
    }
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
    const parts = state.filter(isGroup).map(describeGroup)
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
    state.forEach((node, index) =>
      list.appendChild(
        isGroup(node) ?
          renderGroup(node, [index], { inTrack: false }) :
          renderStrayChips(state, [node])
      )
    )
    container.appendChild(list)

    container.appendChild(renderAddGroupRow(state, { inTrack: false }))
  }

  function persistAndRender() {
    clampValues(state)
    writeInput()
    render()
  }

  // Children that cannot be saved where they are (a course at the top
  // level, a course beside tracks); shown only so they can be removed.
  function renderStrayChips(list, nodes) {
    const chips = document.createElement("div")
    chips.className = "req-chips"
    nodes.forEach(node => chips.appendChild(renderChip(list, node)))
    return chips
  }

  function renderAddGroupRow(list, { inTrack }) {
    const row = document.createElement("div")
    row.className = "req-add-row"

    const addAllOf = document.createElement("button")
    addAllOf.type = "button"
    addAllOf.className = "req-add-btn"
    addAllOf.textContent = inTrack ?
      "+ Add a required group" :
      "+ Add a required group (all of)"
    addAllOf.addEventListener("click", () => {
      list.push(makeGroup(OP.allOf))
      persistAndRender()
    })

    const addChooseN = document.createElement("button")
    addChooseN.type = "button"
    addChooseN.className = "req-add-btn req-add-btn--elective"
    addChooseN.textContent = inTrack ?
      "+ Add an elective group" :
      "+ Add an elective group (choose N of)"
    addChooseN.addEventListener("click", () => {
      list.push(makeGroup(OP.minNumberOf))
      persistAndRender()
    })

    row.append(addAllOf, addChooseN)
    return row
  }

  function renderGroup(node, path, { inTrack }) {
    const el = document.createElement("div")
    el.className = `req-group${inTrack ? " req-group--nested" : ""}`
    el.dataset.mode = node.data.operator === OP.minNumberOf ? "choose" : "all"

    el.appendChild(renderGroupHead(node, path))
    el.appendChild(renderGroupSentence(node))

    if (holdsTracks(node)) {
      el.appendChild(renderTracks(node, path))
      return el
    }

    el.appendChild(renderLeafPicker(node))
    // Only one top-level "Minimum # of" group may hold tracks, and it holds
    // nothing else, so the option appears only on an empty group while no
    // other group holds tracks. Once a track is added, the track list replaces
    // the picker.
    if (
      node.data.operator === OP.minNumberOf &&
      node.children.length === 0 &&
      !state.some(holdsTracks)
    ) {
      el.appendChild(renderAddTrackButton(node))
    }
    return el
  }

  function renderAddTrackButton(group) {
    const addTrack = document.createElement("button")
    addTrack.type = "button"
    addTrack.className = "req-add-track-btn"
    addTrack.textContent = "+ Add a track"
    addTrack.addEventListener("click", () => {
      // The validator requires a group that holds tracks to be elective (the
      // flat required/elective course lists bucket by that flag) with a value
      // of 1; the group's stepper is hidden from here on, and an empty
      // "Minimum # of 0" group is valid and offers this button.
      group.data.elective_flag = true
      group.data.operator_value = 1
      group.children.push(makeTrack())
      persistAndRender()
    })
    return addTrack
  }

  function renderTracks(group, path) {
    const tracks = document.createElement("div")
    tracks.className = "req-tracks"
    const strays = group.children.filter(child => !isTrack(child))
    if (strays.length) {
      tracks.appendChild(renderStrayChips(group.children, strays))
    }
    group.children.forEach((track, index) => {
      if (isTrack(track)) {
        tracks.appendChild(renderTrack(track, [...path, index]))
      }
    })
    tracks.appendChild(renderAddTrackButton(group))
    return tracks
  }

  function renderTrack(node, path) {
    const el = document.createElement("div")
    el.className = "req-track"

    const head = document.createElement("div")
    head.className = "req-track__head"

    const pill = document.createElement("span")
    pill.className = "req-track__pill"
    pill.textContent = "TRACK"

    const title = document.createElement("input")
    title.type = "text"
    title.className = "req-track__title"
    title.value = node.data.title || ""
    title.placeholder = "Track title"
    title.addEventListener("input", event => {
      node.data.title = event.target.value
      writeInput()
    })

    const remove = document.createElement("button")
    remove.type = "button"
    remove.className = "req-group__remove"
    remove.textContent = "✕"
    remove.title = "Remove track"
    remove.addEventListener("click", () => {
      const { list, index } = locate(path)
      list.splice(index, 1)
      persistAndRender()
    })

    head.append(pill, title, remove)

    const description = document.createElement("textarea")
    description.className = "req-track__description"
    description.value = node.data.description || ""
    description.placeholder = "Description shown to learners choosing a track"
    description.rows = 2
    description.addEventListener("input", event => {
      node.data.description = event.target.value
      writeInput()
    })

    const groups = document.createElement("div")
    groups.className = "req-track__groups"
    node.children.forEach((group, index) =>
      groups.appendChild(
        renderGroup(group, [...path, index], { inTrack: true })
      )
    )
    groups.appendChild(renderAddGroupRow(node.children, { inTrack: true }))

    el.append(head, description, groups)
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
    allBtn.textContent = "All"
    allBtn.className = node.data.operator === OP.allOf ? "active" : ""

    const chooseBtn = document.createElement("button")
    chooseBtn.type = "button"
    // The stepper beside the active button supplies the number; the inactive
    // button stands in for it with a literal "N".
    const chooseActive = node.data.operator === OP.minNumberOf
    chooseBtn.textContent = chooseActive ? "At least" : "At least N"
    chooseBtn.className = chooseActive ? "active" : ""

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
    sentence.appendChild(lead)
    // A group that holds tracks is always "Minimum # of" with a value of 1;
    // the toggle and the stepper would only produce a tree the validator
    // rejects.
    if (holdsTracks(node)) {
      const oneTrack = document.createElement("span")
      oneTrack.textContent = "one of these tracks"
      sentence.appendChild(oneTrack)
      return sentence
    }
    sentence.appendChild(segmented)

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
    node.children.forEach(child =>
      chips.appendChild(renderChip(node.children, child))
    )
    picker.appendChild(chips)

    picker.appendChild(renderCombobox(node))
    return picker
  }

  // A chip for any child of `list`: a course, a program, or a group that
  // cannot be saved there (a group inside a group, a course beside tracks),
  // which the badge names so it can be recognized and removed.
  function renderChip(list, child) {
    const chip = document.createElement("span")
    chip.className = "req-chip"
    const badgeText = {
      [NODE.program]:  "PROGRAM",
      [NODE.operator]: "GROUP"
    }[child.data.node_type]
    if (badgeText) {
      const badge = document.createElement("span")
      badge.className = "req-chip__badge"
      badge.textContent = badgeText
      chip.appendChild(badge)
    }
    const label = document.createElement("span")
    label.textContent = leafLabel(child)
    chip.appendChild(label)

    const remove = document.createElement("button")
    remove.type = "button"
    remove.textContent = "✕"
    remove.title = "Remove"
    remove.addEventListener("click", () => {
      list.splice(list.indexOf(child), 1)
      persistAndRender()
    })
    chip.appendChild(remove)
    return chip
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
