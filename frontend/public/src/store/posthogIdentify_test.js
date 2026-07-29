// @flow
import { assert } from "chai"
import sinon from "sinon"
import { actionTypes } from "redux-query"
import posthog from "posthog-js"

import posthogIdentifyMiddleware from "./posthogIdentify"
import { CURRENT_USER_URL } from "../lib/queries/users"

describe("posthogIdentifyMiddleware", () => {
  let sandbox, identifyStub, next, invoke

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    identifyStub = sandbox.stub(posthog, "identify")
    global.SETTINGS = {
      posthog_api_host: "https://posthog.example.com",
      environment:      "test"
    }

    next = sandbox.stub().returnsArg(0)
    invoke = action => posthogIdentifyMiddleware()(next)(action)
  })

  afterEach(() => {
    sandbox.restore()
    delete global.SETTINGS
  })

  it("identifies the user when the current user request succeeds", () => {
    invoke({
      type:     actionTypes.REQUEST_SUCCESS,
      url:      CURRENT_USER_URL,
      entities: { currentUser: { id: 5, global_id: "guid-123" } }
    })

    sinon.assert.calledWith(identifyStub, "guid-123", {
      environment: "test",
      user_id:     5
    })
  })

  it("does not identify a user with no global_id", () => {
    invoke({
      type:     actionTypes.REQUEST_SUCCESS,
      url:      CURRENT_USER_URL,
      entities: { currentUser: { id: 5, global_id: null } }
    })

    sinon.assert.notCalled(identifyStub)
  })

  it("ignores successful requests for other URLs", () => {
    invoke({
      type:     actionTypes.REQUEST_SUCCESS,
      url:      "/api/countries/",
      entities: { currentUser: { id: 5, global_id: "guid-123" } }
    })

    sinon.assert.notCalled(identifyStub)
  })

  it("ignores other action types for the current user URL", () => {
    invoke({
      type:     actionTypes.REQUEST_START,
      url:      CURRENT_USER_URL,
      entities: { currentUser: { id: 5, global_id: "guid-123" } }
    })

    sinon.assert.notCalled(identifyStub)
  })

  it("does not identify when PostHog is not configured", () => {
    global.SETTINGS.posthog_api_host = null

    invoke({
      type:     actionTypes.REQUEST_SUCCESS,
      url:      CURRENT_USER_URL,
      entities: { currentUser: { id: 5, global_id: "guid-123" } }
    })

    sinon.assert.notCalled(identifyStub)
  })

  it("passes the action through to next", () => {
    const action = { type: actionTypes.REQUEST_START, url: CURRENT_USER_URL }
    const result = invoke(action)

    sinon.assert.calledWith(next, action)
    assert.equal(result, action)
  })
})
