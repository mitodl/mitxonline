// @flow
import React from "react"
import sinon from "sinon"
import { shallow } from "enzyme"
import posthog from "posthog-js"

import Header from "./Header"
import { makeUser, makeAnonymousUser } from "../factories/user"

describe("Header component", () => {
  let sandbox, identifyStub

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    identifyStub = sandbox.stub(posthog, "identify")
    global.SETTINGS = { environment: "test" }
  })

  afterEach(() => {
    sandbox.restore()
    delete global.SETTINGS
  })

  const render = currentUser =>
    shallow(
      <Header currentUser={currentUser} cartItemsCount={0} location={null} />
    )

  it("identifies the user to PostHog by their global_id", () => {
    const user = makeUser()

    render(user)

    sinon.assert.calledWith(identifyStub, user.global_id, {
      environment: "test",
      user_id:     user.id
    })
  })

  it("does not identify a user with no global_id", () => {
    const user = makeUser()
    user.global_id = null

    render(user)

    sinon.assert.notCalled(identifyStub)
  })

  it("does not identify an anonymous user", () => {
    render(makeAnonymousUser())

    sinon.assert.notCalled(identifyStub)
  })
})
