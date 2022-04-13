// @flow
import { assert } from "chai"
import sinon from "sinon"

import HeaderApp, { HeaderApp as InnerHeaderApp } from "./HeaderApp"
import IntegrationTestHelper from "../util/integration_test_helper"
import * as notificationsApi from "../lib/notificationsApi"

describe("Top-level HeaderApp", () => {
  let helper, renderPage, getStoredUserMessageStub, removeStoredUserMessageStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    getStoredUserMessageStub = helper.sandbox
      .stub(notificationsApi, "getStoredUserMessage")
      .returns(null)
    removeStoredUserMessageStub = helper.sandbox.stub(
      notificationsApi,
      "removeStoredUserMessage"
    )
    renderPage = helper.configureHOCRenderer(HeaderApp, InnerHeaderApp, {}, {})
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("fetches user data on load and initially renders an empty element", async () => {
    const { inner } = await renderPage()

    assert.notExists(inner.find("div").prop("children"))
    sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")
  })

  it("adds a user notification if a stored message is found in cookies", async () => {
    const userMsg = {
      type: "some-type",
      text: "some text"
    }
    getStoredUserMessageStub.returns(userMsg)
    const { store } = await renderPage()

    const { ui } = store.getState()
    assert.deepEqual(ui.userNotifications, {
      "loaded-user-msg": {
        type:  userMsg.type,
        props: {
          text: userMsg.text
        }
      }
    })
    sinon.assert.calledOnce(removeStoredUserMessageStub)
  })
})
