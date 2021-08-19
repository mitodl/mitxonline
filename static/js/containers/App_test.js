// @flow
import { assert } from "chai"
import sinon from "sinon"

import App, { App as InnerApp } from "./App"
import { routes } from "../lib/urls"
import * as notificationsApi from "../lib/notificationsApi"
import IntegrationTestHelper from "../util/integration_test_helper"

describe("Top-level App", () => {
  let helper, renderPage, getStoredUserMessageStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    getStoredUserMessageStub = helper.sandbox
      .stub(notificationsApi, "getStoredUserMessage")
      .returns(null)
    renderPage = helper.configureHOCRenderer(
      App,
      InnerApp,
      {},
      {
        match:    { url: routes.root },
        location: {
          pathname: routes.root
        }
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("fetches user data on load and initially renders an empty element", async () => {
    const { inner } = await renderPage()

    assert.notExists(inner.find(".app").prop("children"))
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
  })
})
