// @flow
import { assert } from "chai"
import sinon from "sinon"
import { mergeRight } from "ramda"

import App, { App as InnerApp } from "./App"
import { routes } from "../lib/urls"
import IntegrationTestHelper from "../util/integration_test_helper"
import { makeUser, makeUnusedCoupon } from "../factories/user"

describe("Top-level App", () => {
  let helper, renderPage

  beforeEach(() => {
    helper = new IntegrationTestHelper()
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
})
