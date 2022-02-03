import { assert } from "chai"
import { shallow } from "enzyme"
import React from "react"
import { makeAnonymousUser, makeUser } from "../factories/user"
import TopAppBar from "./TopAppBar"

describe("TopAppBar component", () => {
  describe("for anonymous users", () => {
    const user = makeAnonymousUser()
    it("has a button to collapse the menu", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} />)
          .find("button")
          .exists()
      )
    })
    it("has an AnonymousMenu component", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} />)
          .find("AnonymousMenu")
          .exists()
      )
    })
  })
  describe("for logged in users", () => {
    const user = makeUser()
    it("has a UserMenu component", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} />)
          .find("UserMenu")
          .exists()
      )
    })
  })
})
