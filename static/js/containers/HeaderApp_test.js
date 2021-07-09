// @flow
import { assert } from "chai"
import sinon from "sinon"
import { mergeRight } from "ramda"

import HeaderApp, { HeaderApp as InnerHeaderApp } from "./HeaderApp"
import IntegrationTestHelper from "../util/integration_test_helper"
import { makeUser, makeUnusedCoupon } from "../factories/user"

describe("Top-level HeaderApp", () => {
  let helper, renderPage

  beforeEach(() => {
    helper = new IntegrationTestHelper()
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
})
