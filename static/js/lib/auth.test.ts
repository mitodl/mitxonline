import { assert } from "chai"
import sinon from "sinon"
import { makeRegisterAuthResponse } from "../factories/auth"
import { routes } from "../lib/urls"
import IntegrationTestHelper from "../util/integration_test_helper"
import {
  ALL_STATES,
  generateLoginRedirectUrl,
  handleAuthResponse
} from "./auth"

describe("auth lib function", () => {
  it("generateLoginRedirectUrl should generate a url to redirect to after login", () => {
    window.location.assign("/protected/route?var=abc")
    const redirectUrl = generateLoginRedirectUrl(window.location)
    assert.equal(
      redirectUrl,
      `${routes.login.begin}?next=%2Fprotected%2Froute%3Fvar%3Dabc`
    )
  })

  describe("handleAuthResponse", () => {
    let helper: IntegrationTestHelper

    beforeEach(() => {
      helper = new IntegrationTestHelper()
    })
    afterEach(() => {
      helper.cleanup()
    })

    ALL_STATES.forEach(state => {
      it(`calls a corresponding handlers function for state=${state}`, () => {
        const response = makeRegisterAuthResponse({
          state
        })
        const handler = sinon.stub()
        const handlers = {
          [state]: handler
        }
        handleAuthResponse(helper.browserHistory, response, handlers)
        sinon.assert.calledWith(handler, response)
      })
    })
  })
})
