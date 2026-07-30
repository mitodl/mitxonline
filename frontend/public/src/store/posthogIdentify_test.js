// @flow
import { assert } from "chai"
import sinon from "sinon"
import { actionTypes } from "redux-query"
import posthog from "posthog-js"

import posthogIdentifyMiddleware from "./posthogIdentify"
import { CURRENT_USER_URL } from "../lib/queries/users"
import { makeUser } from "../factories/user"

describe("posthogIdentifyMiddleware", () => {
  let sandbox, identifyStub, next, invoke, currentUser

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    identifyStub = sandbox.stub(posthog, "identify")
    global.SETTINGS = {
      posthog_api_host: "https://posthog.example.com",
      environment:      "test"
    }

    currentUser = makeUser()
    next = sandbox.stub().returnsArg(0)
    invoke = action => posthogIdentifyMiddleware()(next)(action)
  })

  afterEach(() => {
    sandbox.restore()
    delete global.SETTINGS
  })

  const currentUserSuccess = (user = currentUser) => ({
    type:     actionTypes.REQUEST_SUCCESS,
    url:      CURRENT_USER_URL,
    entities: { currentUser: user }
  })

  it("identifies the user when the current user request succeeds", () => {
    invoke(currentUserSuccess())

    sinon.assert.calledWith(identifyStub, currentUser.global_id, {
      environment: "test",
      user_id:     currentUser.global_id
    })
  })

  it("does not identify a user with no global_id", () => {
    invoke(currentUserSuccess({ ...currentUser, global_id: null }))

    sinon.assert.notCalled(identifyStub)
  })

  it("ignores successful requests for other URLs", () => {
    invoke({ ...currentUserSuccess(), url: "/api/countries/" })

    sinon.assert.notCalled(identifyStub)
  })

  it("ignores other action types for the current user URL", () => {
    invoke({ ...currentUserSuccess(), type: actionTypes.REQUEST_START })

    sinon.assert.notCalled(identifyStub)
  })

  it("does not identify when PostHog is not configured", () => {
    global.SETTINGS.posthog_api_host = null

    invoke(currentUserSuccess())

    sinon.assert.notCalled(identifyStub)
  })

  it("passes the action through to next", () => {
    const action = currentUserSuccess()
    const result = invoke(action)

    sinon.assert.calledWith(next, action)
    assert.equal(result, action)
  })
})
