// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { shallow, mount } from "enzyme"

import { NOTIFICATION_TYPE_LABELS } from "../constants"

import NotificationPreferences, {
  PreferenceRow,
  lockedChannelsFor,
  descriptionForType
} from "./NotificationPreferences"

// Mirrors a real GET /api/notification-preferences/ response: non_editable
// is an object keyed by notification type, not a flat list of channels.
const makePreferences = (overrides = {}) => ({
  discussion: {
    enabled:            true,
    non_editable:       { new_discussion_post: ["push"] },
    notification_types: {
      new_discussion_post: {
        web:           true,
        push:          false,
        email:         false,
        email_cadence: "Daily",
        info:          ""
      },
      grouped_notification: {
        web:           true,
        push:          false,
        email:         true,
        email_cadence: "Weekly",
        info:          "Covers several activity types"
      }
    },
    ...overrides
  }
})

describe("NotificationPreferences", () => {
  let sandbox, onChangeStub

  const render = (props = {}) =>
    shallow(
      <NotificationPreferences
        preferences={makePreferences()}
        showEmailPreferences={true}
        onChange={onChangeStub}
        {...props}
      />
    )

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onChangeStub = sandbox.stub()
  })

  afterEach(() => {
    sandbox.restore()
  })

  it("renders a group heading using the display label, not the API key", () => {
    const wrapper = render()

    assert.equal(wrapper.find("h3").text(), "Discussions")
  })

  it("renders one row per notification type", () => {
    const wrapper = render()

    assert.lengthOf(wrapper.find(PreferenceRow), 2)
  })

  it("gives each row only the channels its own type locks", () => {
    const wrapper = render({
      preferences: makePreferences({
        non_editable: {
          new_discussion_post:  ["push"],
          grouped_notification: ["email", "push"]
        }
      })
    })

    const byType = {}
    wrapper.find(PreferenceRow).forEach(row => {
      byType[row.props().notificationType] = row.props().nonEditable
    })

    assert.deepEqual(byType, {
      new_discussion_post:  ["push"],
      grouped_notification: ["email", "push"]
    })
  })

  it("renders against a real API payload without throwing", () => {
    // A shallow render will not exercise PreferenceRow, so this mounts the
    // whole tree — the shape of non_editable only breaks on deep render.
    const wrapper = mount(
      <NotificationPreferences
        preferences={makePreferences()}
        showEmailPreferences={true}
        onChange={onChangeStub}
      />
    )

    assert.lengthOf(wrapper.find(".notification-preference-row"), 2)
    // push is locked for new_discussion_post, but web/email are not, and the
    // component must not treat the per-type map as a flat channel list.
    assert.isFalse(
      wrapper.find("input[type='checkbox']").at(0).props().disabled
    )
    wrapper.unmount()
  })

  it("skips groups the API reports as disabled", () => {
    const preferences = makePreferences()
    preferences.discussion.enabled = false

    const wrapper = render({ preferences })

    assert.lengthOf(wrapper.find(PreferenceRow), 0)
  })

  it("shows an empty state when there is nothing to manage", () => {
    const wrapper = render({ preferences: {} })

    assert.include(wrapper.text(), "no notification settings")
  })

  it("passes showEmail down to every row", () => {
    render()
      .find(PreferenceRow)
      .forEach(row => assert.isTrue(row.props().showEmail))

    render({ showEmailPreferences: false })
      .find(PreferenceRow)
      .forEach(row => assert.isFalse(row.props().showEmail))
  })
})

describe("PreferenceRow", () => {
  let sandbox, onChangeStub

  const config = {
    web:           true,
    push:          false,
    email:         false,
    email_cadence: "Daily",
    info:          ""
  }

  const render = (props = {}) =>
    shallow(
      <PreferenceRow
        notificationApp="discussion"
        notificationType="new_discussion_post"
        config={config}
        nonEditable={[]}
        showEmail={true}
        onChange={onChangeStub}
        {...props}
      />
    )

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onChangeStub = sandbox.stub()
  })

  afterEach(() => {
    sandbox.restore()
  })

  it("labels the row with the display name for the type", () => {
    const wrapper = render()

    assert.equal(
      wrapper.find(".notification-preference-label").text(),
      "New discussion posts"
    )
  })

  it("falls back to the raw key for a type it does not know", () => {
    const wrapper = render({ notificationType: "brand_new_type" })

    assert.equal(
      wrapper.find(".notification-preference-label").text(),
      "brand_new_type"
    )
  })

  it("toggling web sends the inverted value for that channel", () => {
    const wrapper = render()

    wrapper.find("input[type='checkbox']").at(0).simulate("change")

    sinon.assert.calledWith(
      onChangeStub,
      "discussion",
      "new_discussion_post",
      "web",
      { value: false }
    )
  })

  it("toggling email sends the inverted value for that channel", () => {
    const wrapper = render()

    wrapper.find("input[type='checkbox']").at(1).simulate("change")

    sinon.assert.calledWith(
      onChangeStub,
      "discussion",
      "new_discussion_post",
      "email",
      { value: true }
    )
  })

  it("changing the cadence sends email_cadence, not value", () => {
    const wrapper = render({ config: { ...config, email: true } })

    wrapper.find("select").simulate("change", { target: { value: "Weekly" } })

    sinon.assert.calledWith(
      onChangeStub,
      "discussion",
      "new_discussion_post",
      "email_cadence",
      { email_cadence: "Weekly" }
    )
  })

  it("hides the cadence control while email delivery is off", () => {
    const wrapper = render()

    assert.lengthOf(wrapper.find("select"), 0)
  })

  it("shows the cadence control once email delivery is on", () => {
    const wrapper = render({ config: { ...config, email: true } })

    assert.lengthOf(wrapper.find("select"), 1)
  })

  it("hides the cadence control when email is locked, even if on", () => {
    const wrapper = render({
      config:      { ...config, email: true },
      nonEditable: ["email"]
    })

    assert.lengthOf(wrapper.find("select"), 0)
  })

  it("gives each checkbox a visible label", () => {
    const text = render({ config: { ...config, email: true } })
      .render()
      .text()

    assert.include(text, "On site")
    assert.include(text, "Email")
  })

  it("gives the cadence select an accessible name", () => {
    const wrapper = render({ config: { ...config, email: true } })

    assert.equal(
      wrapper.find("select").props()["aria-label"],
      "Email frequency for New discussion posts"
    )
  })

  it("renders a description for a type the API sent no info for", () => {
    const wrapper = render({ config: { ...config, info: "" } })

    assert.include(
      wrapper.find(".notification-preference-description").text(),
      "starts a new discussion"
    )
  })

  it("disables the checkboxes the API marks non-editable", () => {
    const wrapper = render({ nonEditable: ["web", "email"] })

    assert.isTrue(wrapper.find("input[type='checkbox']").at(0).props().disabled)
    assert.isTrue(wrapper.find("input[type='checkbox']").at(1).props().disabled)
  })

  it("omits the email controls entirely when email is not shown", () => {
    const wrapper = render({ showEmail: false })

    assert.lengthOf(wrapper.find("input[type='checkbox']"), 1)
    assert.lengthOf(wrapper.find("select"), 0)
  })
})

describe("lockedChannelsFor", () => {
  it("reads the channel list for the requested type", () => {
    const group = { non_editable: { course_updates: ["push"] } }

    assert.deepEqual(lockedChannelsFor(group, "course_updates"), ["push"])
  })

  it("returns an empty list for a type with nothing locked", () => {
    const group = { non_editable: { course_updates: ["push"] } }

    assert.deepEqual(lockedChannelsFor(group, "new_response"), [])
  })

  it("tolerates a group with no non_editable key", () => {
    assert.deepEqual(lockedChannelsFor({}, "course_updates"), [])
  })

  it("still accepts the older flat-array form", () => {
    const group = { non_editable: ["email"] }

    assert.deepEqual(lockedChannelsFor(group, "anything"), ["email"])
  })
})

describe("descriptionForType", () => {
  it("prefers our own copy over the API's info string", () => {
    assert.include(
      descriptionForType("course_updates", "some upstream text"),
      "Announcements and updates"
    )
  })

  it("falls back to the API info for a type we do not know", () => {
    assert.equal(
      descriptionForType("some_new_type", "upstream description"),
      "upstream description"
    )
  })

  it("returns an empty string when there is nothing to show", () => {
    assert.equal(descriptionForType("some_new_type", ""), "")
  })

  it("has copy for every type we label", () => {
    Object.keys(NOTIFICATION_TYPE_LABELS).forEach(type => {
      assert.isNotEmpty(
        descriptionForType(type, ""),
        `no description for ${type}`
      )
    })
  })
})
