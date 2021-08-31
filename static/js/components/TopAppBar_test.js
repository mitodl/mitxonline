// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import TopAppBar from "./TopAppBar"
import AnonymousMenu from "./AnonymousMenu"
import UserMenu from "./UserMenu"

import { routes } from "../lib/urls"
import { makeUser, makeAnonymousUser } from "../factories/user"

describe("TopAppBar component", () => {
  describe("for anonymous users", () => {
    const user = makeAnonymousUser()
    it("has a button to collapse the menu", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find("button")
          .exists()
      )
    })

    it("has an AnonymousMenu component", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find("AnonymousMenu")
          .exists()
      )
    })
  })

  describe("for logged in users", () => {
    const user = makeUser()
    it("has a UserMenu component", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find("UserMenu")
          .exists()
      )
    })
  })
})
