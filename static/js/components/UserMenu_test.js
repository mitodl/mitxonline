// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import UserMenu from "./UserMenu"
import { routes } from "../lib/urls"
import { makeUser } from "../factories/user"

describe("UserMenu component", () => {
  const user = makeUser()

  it("has a link to logout", () => {
    assert.equal(
      shallow(<UserMenu currentUser={user} />)
        .find("a")
        .at(0)
        .prop("href"),
      routes.logout
    )
  })
})
