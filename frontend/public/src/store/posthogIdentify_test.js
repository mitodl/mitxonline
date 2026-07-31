// @flow
import { assert } from "chai"
import sinon from "sinon"
import { actionTypes } from "redux-query"
import posthog from "posthog-js"

import posthogIdentifyMiddleware from "./posthogIdentify"
import { CURRENT_USER_URL } from "../lib/queries/users"
import { makeAnonymousUser, makeUser } from "../factories/user"

describe("posthogIdentifyMiddleware", () => {
  let sandbox,
    identifyStub,
    resetStub,
    getPropertyStub,
    next,
    invoke,
    currentUser

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    identifyStub = sandbox.stub(posthog, "identify")
    resetStub = sandbox.stub(posthog, "reset")
    // Scoped to $user_state on purpose. posthog reads its own feature flags
    // through get_property too, and handing those a string throws
    // "Cannot use 'in' operator", which surfaces as an uncaught error here
    // whenever a stray render elsewhere in the suite checks a flag.
    getPropertyStub = sandbox.stub(posthog, "get_property")
    getPropertyStub.withArgs("$user_state").returns("identified")
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

  it("leaves an authenticated user with no global_id alone", () => {
    invoke(currentUserSuccess({ ...currentUser, global_id: null }))

    sinon.assert.notCalled(identifyStub)
    sinon.assert.notCalled(resetStub)
  })

  it("resets when the browser is anonymous but PostHog is still identified", () => {
    invoke(currentUserSuccess(makeAnonymousUser()))

    sinon.assert.calledWith(getPropertyStub, "$user_state")
    sinon.assert.called(resetStub)
    sinon.assert.notCalled(identifyStub)
  })

  it("does not reset when PostHog already considers the browser anonymous", () => {
    getPropertyStub.withArgs("$user_state").returns("anonymous")

    invoke(currentUserSuccess(makeAnonymousUser()))

    sinon.assert.notCalled(resetStub)
  })

  it("does not reset when the response carries no user", () => {
    invoke({ ...currentUserSuccess(), entities: {} })

    sinon.assert.notCalled(resetStub)
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
