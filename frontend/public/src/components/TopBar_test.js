// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import TopBar from "./TopBar"
import { makeUser, makeAnonymousUser } from "../factories/user"

describe("TopBar component", () => {
  describe("for anonymous users", () => {
    const user = makeAnonymousUser()

    it("has an AnonymousMenu component", () => {
      assert.isOk(
        shallow(<TopBar currentUser={user} location={null} />)
          .find("AnonymousMenu")
          .exists()
      )
    })
  })

  describe("for logged in users", () => {
    const user = makeUser()
    it("has a UserMenu component", () => {
      assert.isOk(
        shallow(<TopBar currentUser={user} location={null} />)
          .find("UserMenu")
          .exists()
      )
    })
  })
})
