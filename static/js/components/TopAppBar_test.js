// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import TopAppBar from "./TopAppBar"

import { routes } from "../lib/urls"
import { makeUser, makeAnonymousUser } from "../factories/user"

describe("TopAppBar component", () => {
  describe("for anonymous users", () => {
    const user = makeAnonymousUser()
    it("has a link to login", () => {
      assert.equal(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find("MixedLink")
          .at(0)
          .prop("dest"),
        routes.login
      )
    })

    it("has a link to register", () => {
      assert.equal(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find("MixedLink")
          .at(1)
          .prop("dest"),
        routes.register.begin
      )
    })

    it("has a button to collapse the menu", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find("button")
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

    it("have MixedLinks for login/registration for mobile view", () => {
      assert.isOk(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find("MixedLink")
          .exists()
      )
    })

    it("have two menu items with authenticated-menu class attributes", () => {
      assert.equal(
        shallow(<TopAppBar currentUser={user} location={null} />)
          .find(".authenticated-menu")
          .getElements().length,
        2
      )
    })
  })
})
